"""Cisco FMC MCP Server implementation."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class FMCMCPServer:
    """Cisco Secure Firewall Management Center MCP Server."""

    def __init__(self, device_name: Optional[str] = None):
        """Initialize the FMC MCP Server.

        Args:
            device_name: Optional FMC device name to bind to at startup.
                         When None the device is resolved per-request from
                         the first active device entry in the database.
        """
        self.device_name = device_name
        self.settings = get_settings()

        self.api_loader = APILoader()
        self._auth_middleware_cache: Dict[str, AuthMiddleware] = {}
        self.security_middleware = SecurityMiddleware()
        self.audit_logger = AuditLogger(device_name or "default")

        self.server = Server("fmc-mcp")

        self.loaded_apis: Dict[str, Dict[str, Any]] = {}
        self.operations: List[Dict[str, Any]] = []

        self._tool_overrides: Dict[str, Dict[str, Any]] = {}
        self._guidance_loaded = False

    def get_auth_middleware(self, device_name: str) -> AuthMiddleware:
        """Get or create an AuthMiddleware for a specific FMC device."""
        if device_name not in self._auth_middleware_cache:
            self._auth_middleware_cache[device_name] = AuthMiddleware(device_name)
        return self._auth_middleware_cache[device_name]

    async def load_api(self, api_name: str) -> bool:
        """Load a specific API definition.

        Args:
            api_name: Registry key (e.g. ``"fmc"``).

        Returns:
            True if loaded successfully.
        """
        api_def = APIRegistry.get_api(api_name)
        if not api_def:
            logger.error("Unknown API: %s", api_name)
            return False

        if not api_def.enabled:
            logger.info("API %s is disabled, skipping", api_name)
            return False

        spec = self.api_loader.load_openapi_spec(api_def.spec_file)
        if not spec:
            logger.error("Failed to load %s specification", api_def.display_name)
            return False

        is_valid, errors = self.api_loader.validate_spec(spec)
        if not is_valid:
            logger.error("Invalid %s spec: %s", api_def.display_name, errors)
            return False

        self.loaded_apis[api_name] = spec

        api_info = self.api_loader.get_api_info(spec)
        logger.info("Loaded %s: %s v%s", api_def.display_name, api_info["title"], api_info["version"])

        counts = self.api_loader.count_endpoints(spec)
        logger.info(
            "%s endpoints — Total: %d, GET: %d, POST: %d, PUT: %d, DELETE: %d",
            api_def.display_name,
            counts["total"], counts["GET"], counts["POST"], counts["PUT"], counts["DELETE"],
        )

        operations = self.api_loader.list_operations(spec)
        for op in operations:
            op["api_name"] = api_name

        self.operations.extend(operations)
        logger.info("Found %d operations in %s", len(operations), api_def.display_name)
        return True

    async def load_guidance_cache(self) -> None:
        """Load tool description overrides from the database into cache."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            overrides = await guidance_service.get_all_tool_overrides()
            self._tool_overrides = {
                op_name: override.to_dict()
                for op_name, override in overrides.items()
            }
            self._guidance_loaded = True
            logger.info("Loaded %d tool description overrides", len(self._tool_overrides))
        except Exception as exc:
            logger.warning("Failed to load guidance cache: %s", exc)
            self._tool_overrides = {}

    async def get_system_prompt(self) -> str:
        """Return the generated system prompt from the guidance service."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            return await guidance_service.generate_system_prompt()
        except Exception as exc:
            logger.warning("Failed to generate system prompt: %s", exc)
            return "Cisco FMC MCP Server — Firewall management and policy automation APIs"

    async def get_workflows_json(self) -> str:
        """Return active workflows as a JSON string for the MCP resource."""
        try:
            from src.services.guidance_service import GuidanceService
            guidance_service = GuidanceService()
            workflows = await guidance_service.list_workflows(active_only=True)
            return json.dumps([w.to_dict() for w in workflows], indent=2)
        except Exception as exc:
            logger.warning("Failed to get workflows: %s", exc)
            return "[]"

    async def load_all_apis(self) -> int:
        """Load all enabled APIs and return the count of successfully loaded APIs."""
        enabled_apis = APIRegistry.get_enabled_apis()
        loaded_count = 0
        for api_def in enabled_apis:
            if await self.load_api(api_def.name):
                loaded_count += 1
        return loaded_count

    def _build_tool_from_operation(self, operation: Dict[str, Any]) -> Tool:
        """Build an MCP Tool from an OpenAPI operation dict."""
        method = operation["method"]
        path = operation["path"]
        operation_id = operation["operation_id"]
        api_name = operation.get("api_name", "fmc")
        summary = operation.get("summary", "")

        tool_name = f"{api_name}_{operation_id}"
        if len(tool_name) > 64:
            tool_name = operation_id[:64]

        if tool_name in self._tool_overrides:
            override = self._tool_overrides[tool_name]
            if override.get("enhanced_description"):
                tool_description = override["enhanced_description"]
            else:
                tool_description = summary or f"{method} {path}"
                tool_description += f"\nEndpoint: {method} {path}"
            if override.get("usage_hint"):
                tool_description += f"\nHint: {override['usage_hint']}"
        else:
            api_display = api_name.replace("_", " ").title()
            tool_description = summary or f"{method} {path}"
            tool_description += f"\nEndpoint: {method} {path}"
            tool_description += f"\nAPI: {api_display}"

        path_params = re.findall(r'\{([^}]+)\}', path)

        # domainUUID is auto-filled from the auth token at call time; don't expose to AI
        _HIDDEN_PATH_PARAMS = {"domainUUID"}

        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in path_params:
            if param in _HIDDEN_PATH_PARAMS:
                continue
            properties[param] = {"type": "string", "description": f"Path parameter: {param}"}
            required.append(param)

        for param in operation.get("parameters", []):
            param_name = param.get("name")
            param_in = param.get("in")
            if param_name and param_in == "query":
                param_schema = param.get("schema", {})
                properties[param_name] = {
                    "type": param_schema.get("type", "string"),
                    "description": param.get("description", f"Query parameter: {param_name}"),
                }
                if param.get("required", False):
                    required.append(param_name)

        if operation.get("requestBody"):
            properties["body"] = {"type": "object", "description": "Request body data"}

        input_schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            input_schema["required"] = required

        return Tool(name=tool_name, description=tool_description, inputSchema=input_schema)

    async def handle_call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        device_name: Optional[str] = None,
    ) -> List[TextContent]:
        """Handle an MCP tool call.

        Args:
            name: Tool name as returned by list_tools.
            arguments: Arguments supplied by the caller.
            device_name: Optional FMC device to target.

        Returns:
            List of TextContent responses.
        """
        try:
            # Strip the "fmc_" prefix to isolate the operation_id
            if "_" in name:
                _, operation_id = name.split("_", 1)
            else:
                operation_id = name

            operation = next(
                (op for op in self.operations if op["operation_id"] == operation_id),
                None,
            )

            if not operation:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Operation {operation_id} not found"}),
                )]

            method = operation["method"]
            path = operation["path"]

            # Authenticate early so we can auto-fill domainUUID from the token
            api_name = operation.get("api_name", "fmc")
            target_device = device_name or self.device_name or "default"
            auth_mw = self.get_auth_middleware(target_device)
            fmc_client = await auth_mw.get_api_client()
            auto_path_params = {}
            if fmc_client.domain_uuid:
                auto_path_params["domainUUID"] = fmc_client.domain_uuid

            # Substitute path parameters; auto_path_params always wins for hidden params
            _HIDDEN_PATH_PARAMS = {"domainUUID"}
            path_params = re.findall(r'\{([^}]+)\}', path)
            for param in path_params:
                if param in auto_path_params and param in _HIDDEN_PATH_PARAMS:
                    path = path.replace(f"{{{param}}}", auto_path_params[param])
                elif param in arguments:
                    path = path.replace(f"{{{param}}}", str(arguments[param]))
                elif param in auto_path_params:
                    path = path.replace(f"{{{param}}}", auto_path_params[param])
                else:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Missing required path parameter: {param}",
                            "required_parameters": [p for p in path_params if p not in auto_path_params],
                        }),
                    )]

            query_params = {
                k: v for k, v in arguments.items()
                if k not in path_params and k != "body"
            }

            try:
                await self.security_middleware.enforce_security(
                    method=method,
                    operation_id=operation_id,
                    path=path,
                )
            except PermissionError as exc:
                error_msg = str(exc)
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
                        "edit_mode_required": True,
                    }),
                )]

            try:
                response = await auth_mw.execute_request(
                    method=method,
                    path=path,
                    api_name=api_name,
                    params=query_params if query_params else None,
                    json_data=arguments.get("body"),
                )

                await self.audit_logger.log_operation(
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    request_body=arguments.get("body"),
                    response_status=200,
                    response_body=response,
                )

                return [TextContent(type="text", text=json.dumps(response, indent=2))]

            except Exception as exc:
                error_msg = str(exc)
                logger.error("API request failed for %s: %s", name, exc)
                await self.audit_logger.log_operation(
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    error_message=error_msg,
                )
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg, "type": type(exc).__name__}),
                )]

        except Exception as exc:
            logger.error("Tool execution failed for %s: %s", name, exc, exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(exc), "type": type(exc).__name__}),
            )]

    async def run(self) -> None:
        """Start the MCP server."""
        try:
            loaded_count = await self.load_all_apis()
            if loaded_count == 0:
                logger.error("Failed to load any APIs, exiting")
                return

            logger.info(
                "Successfully loaded %d API(s) with %d total operations",
                loaded_count, len(self.operations),
            )

            await self.load_guidance_cache()

            @self.server.call_tool()
            async def handle_tool_call(name: str, arguments: dict) -> List[TextContent]:
                return await self.handle_call_tool(name, arguments)

            @self.server.list_tools()
            async def list_tools() -> List[Tool]:
                tools = [self._build_tool_from_operation(op) for op in self.operations]
                logger.info("Listing %d tools", len(tools))
                return tools

            logger.info(
                "Registered tool handlers for %d operations across %d API(s)",
                len(self.operations), loaded_count,
            )

            @self.server.list_resources()
            async def list_resources() -> List[Resource]:
                return [
                    Resource(
                        uri="fmc://guidance/system-prompt",
                        name="FMC API Guidance System Prompt",
                        description=(
                            "Guidance for using Cisco FMC APIs including operation selection, "
                            "domain UUID resolution, workflows, and best practices"
                        ),
                        mimeType="text/plain",
                    ),
                    Resource(
                        uri="fmc://guidance/workflows",
                        name="Common FMC Workflows",
                        description="Pre-defined workflows for common firewall automation tasks",
                        mimeType="application/json",
                    ),
                ]

            @self.server.read_resource()
            async def read_resource(uri: str) -> str:
                if uri == "fmc://guidance/system-prompt":
                    return await self.get_system_prompt()
                elif uri == "fmc://guidance/workflows":
                    return await self.get_workflows_json()
                raise ValueError(f"Unknown resource URI: {uri}")

            logger.info("Registered MCP resources for FMC API guidance")

            edit_mode = await self.security_middleware.is_edit_mode_enabled()
            logger.info("Edit mode: %s", "ENABLED" if edit_mode else "DISABLED (read-only)")

            async with stdio_server() as (read_stream, write_stream):
                logger.info("FMC MCP Server started via stdio")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )

        except Exception as exc:
            logger.error("Server error: %s", exc, exc_info=True)
            raise

    async def cleanup(self) -> None:
        """Release all resources."""
        for device, auth_mw in self._auth_middleware_cache.items():
            try:
                await auth_mw.close()
            except Exception as exc:
                logger.warning("Error closing auth middleware for '%s': %s", device, exc)
        self._auth_middleware_cache.clear()
        logger.info("Cleanup completed")

