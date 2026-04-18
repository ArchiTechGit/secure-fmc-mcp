"""API loader for loading the FMC OpenAPI specification and creating MCP tools."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FMC_SPEC_FILE = "fmc_oas3.json"


class APILoader:
    """Loader for the FMC OpenAPI specification."""

    def __init__(self, specs_dir: str = "openapi_specs"):
        self.specs_dir = Path(specs_dir)
        self.loaded_specs: Dict[str, Dict[str, Any]] = {}

    def load_openapi_spec(self, spec_file: str) -> Optional[Dict[str, Any]]:
        """Load an OpenAPI specification from file."""
        spec_path = self.specs_dir / spec_file

        if not spec_path.exists():
            logger.error("OpenAPI spec file not found: %s", spec_path)
            return None

        try:
            with open(spec_path, "r") as f:
                spec = json.load(f)
            logger.info("Successfully loaded OpenAPI spec: %s", spec_file)
            return spec
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse OpenAPI spec %s: %s", spec_file, exc)
            return None
        except Exception as exc:
            logger.error("Error loading OpenAPI spec %s: %s", spec_file, exc)
            return None

    def get_api_info(self, spec: Dict[str, Any]) -> Dict[str, str]:
        """Extract API info (title, version, description) from spec."""
        info = spec.get("info", {})
        return {
            "title": info.get("title", "Unknown API"),
            "version": info.get("version", "0.0.0"),
            "description": info.get("description", ""),
        }

    def count_endpoints(self, spec: Dict[str, Any]) -> Dict[str, int]:
        """Count endpoints by HTTP method."""
        counts: Dict[str, int] = {"GET": 0, "POST": 0, "PUT": 0, "DELETE": 0, "PATCH": 0, "total": 0}
        for path_item in spec.get("paths", {}).values():
            for method in ("get", "post", "put", "delete", "patch"):
                if method in path_item:
                    counts[method.upper()] += 1
                    counts["total"] += 1
        return counts

    def list_operations(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return a list of all operations from the spec."""
        operations = []
        for path, path_item in spec.get("paths", {}).items():
            for method in ("get", "post", "put", "delete", "patch", "head", "options"):
                if method not in path_item:
                    continue
                operation = path_item[method]
                operations.append({
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", f"{method}_{path}"),
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": operation.get("tags", []),
                    "parameters": operation.get("parameters", []),
                    "requestBody": operation.get("requestBody"),
                })
        return operations

    def get_base_url(self, spec: Dict[str, Any]) -> Optional[str]:
        """Extract the first server URL from the spec."""
        servers = spec.get("servers", [])
        if servers:
            return servers[0].get("url")
        return None

    def validate_spec(self, spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate basic OpenAPI spec structure."""
        errors = []
        if "openapi" not in spec:
            errors.append("Missing 'openapi' version field")
        if "info" not in spec:
            errors.append("Missing 'info' section")
        elif "title" not in spec["info"]:
            errors.append("Missing 'info.title' field")
        if "paths" not in spec:
            errors.append("Missing 'paths' section")
        elif not spec["paths"]:
            errors.append("'paths' section is empty")
        return len(errors) == 0, errors

    def load_all_specs(self) -> Dict[str, Dict[str, Any]]:
        """Load the FMC OpenAPI specification.

        Returns a dict keyed by API name (``"fmc"``) mapping to the spec dict.
        """
        spec = self.load_openapi_spec(FMC_SPEC_FILE)
        if not spec:
            logger.error("Failed to load FMC OpenAPI spec (%s)", FMC_SPEC_FILE)
            return {}

        is_valid, errors = self.validate_spec(spec)
        if not is_valid:
            logger.error("Invalid FMC OpenAPI spec: %s", errors)
            return {}

        self.loaded_specs = {"fmc": spec}
        logger.info("Validated and loaded FMC API spec")
        return self.loaded_specs
