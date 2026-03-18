"""Main Nexus Dashboard MCP Server implementation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Use MCP SDK properly
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

from src.config.settings import get_settings
from src.core.api_loader import APILoader
from src.core.api_registry import APIRegistry
from src.middleware.auth import AuthMiddleware
from src.middleware.logging import AuditLogger
from src.middleware.security import SecurityMiddleware

logger = logging.getLogger(__name__)


class NexusDashboardMCP:
    """Nexus Dashboard MCP Server."""

    def __init__(self, cluster_name: Optional[str] = None):
        """Initialize Nexus Dashboard MCP Server.

        Args:
            cluster_name: Optional name of the Nexus Dashboard cluster to bind to.
                          When None, the cluster is resolved per-request from the
                          authenticated user's cluster assignment.
        """
        self.cluster_name = cluster_name
        self.settings = get_settings()

        # Initialize components
        self.api_loader = APILoader()
        # Auth middleware is lazily created per cluster via get_auth_middleware()
        self._auth_middleware_cache: Dict[str, AuthMiddleware] = {}
        self.security_middleware = SecurityMiddleware()
        # Audit logger uses "default" when no cluster is bound at init time
        self.audit_logger = AuditLogger(cluster_name or "default")

        # MCP server
        self.server = Server("nexus-dashboard-mcp")

        # Loaded specs and tools
        self.loaded_apis: Dict[str, Dict[str, Any]] = {}
        self.operations: List[Dict[str, Any]] = []

        # Guidance cache
        self._tool_overrides: Dict[str, Dict[str, Any]] = {}
        self._guidance_loaded = False

    def get_auth_middleware(self, cluster_name: str) -> AuthMiddleware:
        """Get or create AuthMiddleware for a specific cluster.

        Args:
            cluster_name: Name of the cluster to get middleware for.

        Returns:
            AuthMiddleware instance for the specified cluster.
        """
        if cluster_name not in self._auth_middleware_cache:
            self._auth_middleware_cache[cluster_name] = AuthMiddleware(cluster_name)
        return self._auth_middleware_cache[cluster_name]

    async def load_api(self, api_name: str) -> bool:
        """Load a specific Nexus Dashboard API.

        Args:
            api_name: Name of the API to load

        Returns:
            True if loaded successfully, False otherwise
        """
        api_def = APIRegistry.get_api(api_name)
        if not api_def:
            logger.error(f"Unknown API: {api_name}")
            return False

        if not api_def.enabled:
            logger.info(f"API {api_name} is disabled, skipping")
            return False

        spec = self.api_loader.load_openapi_spec(api_def.spec_file)
        if not spec:
            logger.error(f"Failed to load {api_def.display_name} specification")
            return False

        # Validate spec
        is_valid, errors = self.api_loader.validate_spec(spec)
        if not is_valid:
            logger.error(f"Invalid {api_def.display_name} spec: {errors}")
            return False

        # Store loaded spec
        self.loaded_apis[api_name] = spec

        # Get API info
        api_info = self.api_loader.get_api_info(spec)
        logger.info(
            f"Loaded {api_def.display_name}: {api_info['title']} v{api_info['version']}"
        )

        # Count endpoints
        counts = self.api_loader.count_endpoints(spec)
        logger.info(
            f"{api_def.display_name} endpoints - Total: {counts['total']}, "
            f"GET: {counts['GET']}, POST: {counts['POST']}, "
            f"PUT: {counts['PUT']}, DELETE: {counts['DELETE']}"
        )

        # Add operations with API name prefix
        operations = self.api_loader.list_operations(spec)
        for op in operations:
            op["api_name"] = api_name  # Tag operation with API name

        self.operations.extend(operations)
        logger.info(f"Found {len(operations)} operations in {api_def.display_name}")

        return True

    async def load_guidance_cache(self) -> None:
        """Load tool description overrides from database into cache."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            overrides = await guidance_service.get_all_tool_overrides()
            self._tool_overrides = {
                op_name: override.to_dict()
                for op_name, override in overrides.items()
            }
            self._guidance_loaded = True
            logger.info(f"Loaded {len(self._tool_overrides)} tool description overrides")
        except Exception as e:
            logger.warning(f"Failed to load guidance cache: {e}")
            self._tool_overrides = {}

    async def get_system_prompt(self) -> str:
        """Get the generated system prompt from guidance service."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            return await guidance_service.generate_system_prompt()
        except Exception as e:
            logger.warning(f"Failed to generate system prompt: {e}")
            return "Nexus Dashboard MCP Server - Network automation APIs"

    async def get_workflows_json(self) -> str:
        """Get workflows as JSON for MCP resource."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            workflows = await guidance_service.list_workflows(active_only=True)
            return json.dumps([w.to_dict() for w in workflows], indent=2)
        except Exception as e:
            logger.warning(f"Failed to get workflows: {e}")
            return "[]"

    async def load_all_apis(self) -> int:
        """Load all enabled APIs.

        Returns:
            Number of APIs loaded successfully
        """
        enabled_apis = APIRegistry.get_enabled_apis()
        loaded_count = 0

        for api_def in enabled_apis:
            success = await self.load_api(api_def.name)
            if success:
                loaded_count += 1

        return loaded_count

    def _build_tool_from_operation(self, operation: Dict[str, Any]) -> Tool:
        """Build MCP Tool from operation.

        Args:
            operation: Operation dictionary (includes api_name)

        Returns:
            Tool instance
        """
        method = operation["method"]
        path = operation["path"]
        operation_id = operation["operation_id"]
        api_name = operation.get("api_name", "manage")  # Get API name from operation
        summary = operation.get("summary", "")
        description = operation.get("description", summary)

        # Create tool name - truncate if too long (max 64 chars for MCP)
        tool_name = f"{api_name}_{operation_id}"
        if len(tool_name) > 64:
            # Use just operation_id, truncated if needed
            tool_name = operation_id[:64]

        # Build tool description
        if tool_name in self._tool_overrides:
            override = self._tool_overrides[tool_name]
            if override.get("enhanced_description"):
                # Enhanced description replaces the default
                tool_description = override["enhanced_description"]
            else:
                # Default format with better structure
                tool_description = summary or f"{method} {path}"
                tool_description += f"\nEndpoint: {method} {path}"
            # Usage hint is always supplementary
            if override.get("usage_hint"):
                tool_description += f"\nHint: {override['usage_hint']}"
        else:
            # Default format with better structure
            api_display = api_name.replace("_", " ").title()
            tool_description = summary or f"{method} {path}"
            tool_description += f"\nEndpoint: {method} {path}"
            tool_description += f"\nAPI: {api_display}"

        # Extract path parameters from path (e.g., {fabricName}, {switchId})
        import re
        path_params = re.findall(r'\{([^}]+)\}', path)

        # Build input schema with parameters
        properties = {}
        required = []

        # Add path parameters
        for param in path_params:
            properties[param] = {
                "type": "string",
                "description": f"Path parameter: {param}"
            }
            required.append(param)

        # Add query parameters from OpenAPI spec
        for param in operation.get("parameters", []):
            param_name = param.get("name")
            param_in = param.get("in")
            param_required = param.get("required", False)
            param_schema = param.get("schema", {})
            param_desc = param.get("description", "")

            if param_name and param_in == "query":
                properties[param_name] = {
                    "type": param_schema.get("type", "string"),
                    "description": param_desc or f"Query parameter: {param_name}"
                }
                if param_required:
                    required.append(param_name)

        # Add body parameter if request body is defined
        if operation.get("requestBody"):
            properties["body"] = {
                "type": "object",
                "description": "Request body data"
            }

        input_schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            input_schema["required"] = required

        return Tool(
            name=tool_name,
            description=tool_description,
            inputSchema=input_schema
        )

    async def handle_call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        cluster_name: Optional[str] = None,
    ) -> List[TextContent]:
        """Handle tool execution.

        Args:
            name: Tool name
            arguments: Tool arguments
            cluster_name: Optional cluster to target. Defaults to self.cluster_name
                          and then falls back to "default".

        Returns:
            List of TextContent responses
        """
        try:
            # Find operation from tool name
            # Handle both "manage_operationId" and just "operationId" formats
            if "_" in name:
                api_name, operation_id = name.split("_", 1)
            else:
                api_name = "manage"  # Default to manage API
                operation_id = name

            operation = next(
                (op for op in self.operations if op["operation_id"] == operation_id),
                None
            )

            if not operation:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Operation {operation_id} not found"})
                )]

            method = operation["method"]
            path = operation["path"]

            # Substitute path parameters (e.g., {fabricName} -> actual value)
            import re
            path_params = re.findall(r'\{([^}]+)\}', path)
            for param in path_params:
                if param in arguments:
                    path = path.replace(f"{{{param}}}", str(arguments[param]))
                else:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Missing required path parameter: {param}",
                            "required_parameters": path_params
                        })
                    )]

            # Separate path params from query params for the request
            query_params = {k: v for k, v in arguments.items() if k not in path_params and k != "body"}

            # Check security
            try:
                await self.security_middleware.enforce_security(
                    method=method,
                    operation_id=operation_id,
                    path=path,
                )
            except PermissionError as e:
                error_msg = str(e)
                await self.audit_logger.log_operation(
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    error_message=error_msg,
                )
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": error_msg,
                        "type": "PermissionError",
                        "edit_mode_required": True
                    })
                )]

            # Get API name from operation
            api_name = operation.get("api_name", "manage")

            # Resolve target cluster: caller arg > instance binding > "default"
            target_cluster = cluster_name or self.cluster_name or "default"
            auth_mw = self.get_auth_middleware(target_cluster)

            # Execute API request
            try:
                response = await auth_mw.execute_request(
                    method=method,
                    path=path,
                    api_name=api_name,
                    params=query_params if query_params else None,
                    json_data=arguments.get("body"),
                )

                # Log success
                await self.audit_logger.log_operation(
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    request_body=arguments.get("body"),
                    response_status=200,
                    response_body=response,
                )

                return [TextContent(
                    type="text",
                    text=json.dumps(response, indent=2)
                )]

            except Exception as e:
                error_msg = str(e)
                logger.error(f"API request failed for {name}: {e}")

                await self.audit_logger.log_operation(
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    error_message=error_msg,
                )

                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": error_msg,
                        "type": type(e).__name__
                    })
                )]

        except Exception as e:
            logger.error(f"Tool execution failed for {name}: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "type": type(e).__name__
                })
            )]

    async def run(self):
        """Run the MCP server."""
        try:
            # Load all enabled APIs
            loaded_count = await self.load_all_apis()
            if loaded_count == 0:
                logger.error("Failed to load any APIs, exiting")
                return

            logger.info(f"Successfully loaded {loaded_count} APIs with {len(self.operations)} total operations")

            # Load guidance cache for enhanced tool descriptions
            await self.load_guidance_cache()

            # Register tool handler
            @self.server.call_tool()
            async def handle_tool_call(name: str, arguments: dict) -> List[TextContent]:
                return await self.handle_call_tool(name, arguments)

            # Register tools
            @self.server.list_tools()
            async def list_tools() -> List[Tool]:
                tools = []
                for operation in self.operations:  # Register all operations
                    tool = self._build_tool_from_operation(operation)
                    tools.append(tool)
                logger.info(f"Listing {len(tools)} tools")
                return tools

            logger.info(f"Registered tool handlers for {len(self.operations)} operations across {loaded_count} APIs")

            # Register MCP resources for guidance
            @self.server.list_resources()
            async def list_resources() -> List[Resource]:
                return [
                    Resource(
                        uri="nexus://guidance/system-prompt",
                        name="API Guidance System Prompt",
                        description="Complete guidance for using Nexus Dashboard APIs including API selection, workflows, and best practices",
                        mimeType="text/plain"
                    ),
                    Resource(
                        uri="nexus://guidance/workflows",
                        name="Common Workflows",
                        description="Pre-defined workflows for common network automation tasks",
                        mimeType="application/json"
                    )
                ]

            @self.server.read_resource()
            async def read_resource(uri: str) -> str:
                if uri == "nexus://guidance/system-prompt":
                    return await self.get_system_prompt()
                elif uri == "nexus://guidance/workflows":
                    return await self.get_workflows_json()
                else:
                    raise ValueError(f"Unknown resource URI: {uri}")

            logger.info("Registered MCP resources for API guidance")

            # Log edit mode status from database
            edit_mode = await self.security_middleware.is_edit_mode_enabled()
            logger.info(f"Edit mode (from database): {'ENABLED' if edit_mode else 'DISABLED (read-only)'}")

            # Start stdio server
            async with stdio_server() as (read_stream, write_stream):
                logger.info("Nexus Dashboard MCP Server started via stdio")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )

        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise

    async def cleanup(self):
        """Cleanup resources."""
        for cluster, auth_mw in self._auth_middleware_cache.items():
            try:
                await auth_mw.close()
            except Exception as e:
                logger.warning(f"Error closing auth middleware for cluster '{cluster}': {e}")
        self._auth_middleware_cache.clear()
        logger.info("Cleanup completed")
