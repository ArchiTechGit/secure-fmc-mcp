"""Authentication middleware for FMC API requests."""

import logging
from typing import Any, Callable, Dict, Optional

from src.services.credential_manager import CredentialManager
from src.services.fmc_api import FMCAPIClient

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Middleware for handling authentication to the Cisco FMC REST API."""

    def __init__(self, cluster_name: str = "default"):
        """Initialize authentication middleware.

        Args:
            cluster_name: Name of the FMC device entry to authenticate with.
        """
        self.cluster_name = cluster_name
        self.credential_manager = CredentialManager()
        self.api_client: Optional[FMCAPIClient] = None

    async def get_api_client(self) -> FMCAPIClient:
        """Get or create an authenticated FMC API client.

        Returns:
            Authenticated FMCAPIClient instance.

        Raises:
            RuntimeError: If credentials are missing or authentication fails.
        """
        if self.api_client is not None:
            return self.api_client

        credentials = None
        if self.cluster_name == "default":
            credentials = await self.credential_manager.get_first_active_cluster_credentials()
            if credentials:
                self.cluster_name = credentials["name"]
                logger.info("Using first active FMC device: %s", self.cluster_name)
        else:
            credentials = await self.credential_manager.get_credentials(self.cluster_name)

        if not credentials:
            raise RuntimeError(
                f"No credentials found for FMC device '{self.cluster_name}'. "
                "Please configure a device in the web UI first."
            )

        self.api_client = FMCAPIClient(
            base_url=credentials["url"],
            username=credentials["username"],
            password=credentials["password"],
            verify_ssl=credentials["verify_ssl"],
        )

        authenticated = await self.api_client.authenticate()
        if not authenticated:
            raise RuntimeError(
                f"Failed to authenticate with FMC device '{self.cluster_name}'"
            )

        logger.info("Successfully authenticated with FMC device '%s'", self.cluster_name)
        return self.api_client

    async def execute_request(
        self,
        method: str,
        path: str,
        api_name: str = "fmc",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an authenticated FMC API request.

        The FMC OAS paths are absolute (e.g. /api/fmc_config/v1/domain/{domainUUID}/...)
        so no base-path prefix is added here.

        Args:
            method: HTTP method.
            path: API path from the OAS spec (already fully qualified).
            api_name: Ignored — retained for interface compatibility.
            params: Optional query parameters.
            json_data: Optional JSON request body.

        Returns:
            Parsed response as a dictionary.
        """
        client = await self.get_api_client()

        try:
            response = await client.request(
                method=method,
                path=path,
                params=params,
                json_data=json_data,
            )

            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json()

            return {"data": response.text, "status_code": response.status_code}

        except Exception as exc:
            logger.error("FMC API request failed: %s %s — %s", method, path, exc)
            raise RuntimeError(f"FMC API request failed: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying API client connection."""
        if self.api_client:
            await self.api_client.close()
            self.api_client = None

    def __call__(self, func: Callable) -> Callable:
        """Decorator that ensures authentication before calling a function."""
        async def wrapper(*args, **kwargs):
            await self.get_api_client()
            return await func(*args, **kwargs)
        return wrapper
