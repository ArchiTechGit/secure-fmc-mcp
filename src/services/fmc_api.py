"""Cisco Secure Firewall Management Center (FMC) API client."""

import logging
from typing import Any, Dict, Optional

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

FMC_AUTH_PATH = "/api/fmc_platform/v1/auth/generatetoken"
FMC_REFRESH_PATH = "/api/fmc_platform/v1/auth/refreshtoken"
FMC_REVOKE_PATH = "/api/fmc_platform/v1/auth/revokeaccess"


class FMCAPIClient:
    """Client for authenticating and making requests to the Cisco FMC REST API.

    FMC uses a token-based auth flow:
      1. POST /api/fmc_platform/v1/auth/generatetoken with Basic auth
      2. Response headers contain X-auth-access-token, X-auth-refresh-token,
         DOMAIN_UUID, and global_DOMAIN_UUID
      3. Subsequent requests send X-auth-access-token header
      4. Tokens can be refreshed via /api/fmc_platform/v1/auth/refreshtoken
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.settings = get_settings()

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.domain_uuid: Optional[str] = None
        self.global_domain_uuid: Optional[str] = None

        self.client = httpx.AsyncClient(
            verify=verify_ssl,
            timeout=httpx.Timeout(self.settings.api_timeout),
            follow_redirects=True,
        )

    async def authenticate(self) -> bool:
        """Generate an FMC access token using HTTP Basic authentication.

        Returns:
            True if token generation succeeded, False otherwise.
        """
        try:
            url = f"{self.base_url}{FMC_AUTH_PATH}"
            response = await self.client.post(
                url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code in (200, 204):
                self.access_token = response.headers.get("X-auth-access-token")
                self.refresh_token = response.headers.get("X-auth-refresh-token")
                self.domain_uuid = response.headers.get("DOMAIN_UUID")
                self.global_domain_uuid = response.headers.get("global_DOMAIN_UUID")

                if self.access_token:
                    logger.info(
                        "FMC authentication successful (domain_uuid=%s)", self.domain_uuid
                    )
                    return True

            logger.error("FMC authentication failed with status %s", response.status_code)
            return False

        except Exception as exc:
            logger.error("FMC authentication error: %s", exc)
            return False

    async def refresh_access_token(self) -> bool:
        """Refresh the current access token without re-authenticating.

        Returns:
            True if refresh succeeded, False otherwise.
        """
        if not self.refresh_token:
            return await self.authenticate()

        try:
            url = f"{self.base_url}{FMC_REFRESH_PATH}"
            response = await self.client.post(
                url,
                headers={
                    "X-auth-access-token": self.access_token or "",
                    "X-auth-refresh-token": self.refresh_token,
                },
            )

            if response.status_code in (200, 204):
                new_access = response.headers.get("X-auth-access-token")
                new_refresh = response.headers.get("X-auth-refresh-token")
                if new_access:
                    self.access_token = new_access
                if new_refresh:
                    self.refresh_token = new_refresh
                logger.info("FMC token refreshed successfully")
                return True

            logger.warning("Token refresh failed (%s), re-authenticating", response.status_code)
            return await self.authenticate()

        except Exception as exc:
            logger.warning("Token refresh error: %s — re-authenticating", exc)
            return await self.authenticate()

    def _auth_headers(self) -> Dict[str, str]:
        """Build the auth header dict for an authenticated request."""
        if not self.access_token:
            raise RuntimeError("Not authenticated — call authenticate() first")
        return {"X-auth-access-token": self.access_token}

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make an authenticated request to the FMC REST API.

        Automatically re-authenticates once on a 401 response.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path (e.g. /api/fmc_config/v1/domain/{domainUUID}/object/networks)
            params: Optional query parameters
            json_data: Optional JSON request body
            headers: Optional additional headers

        Returns:
            httpx.Response

        Raises:
            RuntimeError: If not authenticated
            httpx.HTTPStatusError: On non-2xx responses after retries
        """
        if not self.access_token:
            authenticated = await self.authenticate()
            if not authenticated:
                raise RuntimeError("Failed to authenticate with FMC")

        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"

        max_retries = self.settings.api_retry_attempts
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            request_headers = {**(headers or {}), **self._auth_headers()}

            try:
                response = await self.client.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                )

                if response.status_code == 401 and attempt == 0:
                    logger.warning("Received 401 from FMC, refreshing token and retrying")
                    refreshed = await self.refresh_access_token()
                    if not refreshed:
                        raise RuntimeError("Re-authentication failed after 401")
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                    continue
                raise

            except Exception as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    logger.warning("Request error (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                    continue
                raise

        if last_exception:
            raise last_exception

    async def revoke_token(self) -> None:
        """Revoke the current access token."""
        if not self.access_token:
            return
        try:
            url = f"{self.base_url}{FMC_REVOKE_PATH}"
            await self.client.delete(url, headers=self._auth_headers())
            logger.info("FMC token revoked")
        except Exception as exc:
            logger.warning("Failed to revoke FMC token: %s", exc)
        finally:
            self.access_token = None
            self.refresh_token = None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
