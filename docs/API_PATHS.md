# FMC API Path Reference

## API Base Paths

The Cisco FMC REST API uses two base path roots:

### Configuration API (`fmc_config`)
**Base Path**: `/api/fmc_config/v1/domain/{domainUUID}`

Most operations use this root. The `domainUUID` path parameter identifies the administrative domain (returned as the `DOMAIN_UUID` header when generating an auth token).

**Example Endpoints**:
- List Network Objects: `GET /api/fmc_config/v1/domain/{domainUUID}/object/networks`
- Get Access Policy: `GET /api/fmc_config/v1/domain/{domainUUID}/policy/accesspolicies/{objectId}`
- List Devices: `GET /api/fmc_config/v1/domain/{domainUUID}/devices/devicerecords`
- Deploy Changes: `POST /api/fmc_config/v1/domain/{domainUUID}/deployment/deploymentrequests`

### Platform API (`fmc_platform`)
**Base Path**: `/api/fmc_platform/v1`

Used for authentication and platform-level operations (no domainUUID required).

**Example Endpoints**:
- Generate Token: `POST /api/fmc_platform/v1/auth/generatetoken`
- Refresh Token: `POST /api/fmc_platform/v1/auth/refreshtoken`
- Server Version: `GET /api/fmc_platform/v1/info/serverversion`
- Available Domains: `GET /api/fmc_platform/v1/info/domain`

## FMC OpenAPI Specification

The FMC spec (`fmc_oas3.json`) defines paths that are already fully qualified — they include the complete path from `/api/...` onward. This means the MCP auth middleware passes paths through directly without prepending a base path.

```json
{
  "openapi": "3.0.0",
  "servers": [
    {
      "url": "https://{fmc_host}",
      "variables": {
        "fmc_host": {
          "default": "192.168.1.1"
        }
      }
    }
  ],
  "paths": {
    "/api/fmc_config/v1/domain/{domainUUID}/object/networks": {
      "get": {
        "operationId": "getAllNetworkObjects",
        "summary": "Get all network objects",
        "parameters": [
          {"name": "domainUUID", "in": "path", "required": true},
          {"name": "limit", "in": "query"},
          {"name": "offset", "in": "query"},
          {"name": "filter", "in": "query"}
        ]
      }
    }
  }
}
```

**Key Points**:
- Paths in the spec are already complete (e.g., `/api/fmc_config/v1/domain/{domainUUID}/object/networks`)
- `domainUUID` is a required path parameter for all `fmc_config` operations
- The FMC host is the `base_url` stored in the device credentials

## Implementation in MCP Server

### Path Construction Flow

1. **API Loader** (`src/core/api_loader.py`):
   - Reads `fmc_oas3.json`
   - Extracts fully qualified paths (e.g., `/api/fmc_config/v1/domain/{domainUUID}/object/networks`)
   - Identifies path parameters like `{domainUUID}`, `{objectId}`, etc.

2. **MCP Server** (`src/core/mcp_server.py`):
   - Builds a tool with `domainUUID` as a required input
   - Substitutes `{domainUUID}` before sending the request

3. **Auth Middleware** (`src/middleware/auth.py`):
   - FMC paths are already fully qualified — no prefix is added
   - Passes path directly to `FMCAPIClient`

4. **FMC API Client** (`src/services/fmc_api.py`):
   - Receives full path: `/api/fmc_config/v1/domain/{domainUUID}/object/networks`
   - Joins with base_url: `https://192.168.1.1`
   - Final URL: `https://192.168.1.1/api/fmc_config/v1/domain/{domainUUID}/object/networks`

## Authentication Endpoints

### Generate Token
**Endpoint**: `POST /api/fmc_platform/v1/auth/generatetoken`
**Auth**: HTTP Basic (username:password)

**Response Headers**:
```
X-auth-access-token: <token>
X-auth-refresh-token: <refresh-token>
DOMAIN_UUID: <default-domain-uuid>
global_DOMAIN_UUID: <global-domain-uuid>
```

The `DOMAIN_UUID` header value is what you use as `domainUUID` in all `fmc_config` paths.

### Refresh Token
**Endpoint**: `POST /api/fmc_platform/v1/auth/refreshtoken`
**Headers**: `X-auth-access-token`, `X-auth-refresh-token`

### Revoke Token
**Endpoint**: `DELETE /api/fmc_platform/v1/auth/revokeaccess`
**Headers**: `X-auth-access-token`

## Common Issues and Solutions

### Issue: 404 Not Found

**Symptom**: API returns 404 when calling endpoints

**Possible Causes**:
1. Wrong `domainUUID` — use the UUID returned in `DOMAIN_UUID` header at login
2. Wrong FMC version — some endpoints differ between 6.x and 7.x
3. Service not running or feature not licensed

**Debugging Steps**:
```bash
# Verify FMC is reachable and get token
curl -k -X POST https://YOUR_FMC_IP/api/fmc_platform/v1/auth/generatetoken \
  -u admin:password -v 2>&1 | grep -i "domain_uuid\|access-token\|< HTTP"

# Test config endpoint with domain UUID
curl -k https://YOUR_FMC_IP/api/fmc_config/v1/domain/YOUR_DOMAIN_UUID/object/networks \
  -H "X-auth-access-token: YOUR_TOKEN"
```

### Issue: 401 Unauthorized

**Symptom**: API returns 401

**Possible Causes**:
1. Token expired (FMC tokens have a 30-minute lifetime)
2. Invalid credentials
3. User lacks REST API access rights in FMC

**Solution**: `FMCAPIClient` automatically refreshes tokens on 401. If repeated failures occur, check user permissions in FMC under System > Users.

### Issue: 422 Unprocessable Entity

**Symptom**: Write operation fails with 422

**Possible Cause**: Request body schema mismatch. Use the FMC API Explorer (built into FMC UI at `/api/api-explorer`) to validate the expected schema.

## Testing API Paths

### Manual Testing

```bash
# Step 1: Authenticate and capture domainUUID
RESPONSE=$(curl -k -s -D - -X POST \
  https://YOUR_FMC_IP/api/fmc_platform/v1/auth/generatetoken \
  -u admin:password)

TOKEN=$(echo "$RESPONSE" | grep -i "x-auth-access-token:" | awk '{print $2}' | tr -d '\r')
DOMAIN=$(echo "$RESPONSE" | grep -i "^domain_uuid:" | awk '{print $2}' | tr -d '\r')

# Step 2: List network objects
curl -k "https://YOUR_FMC_IP/api/fmc_config/v1/domain/${DOMAIN}/object/networks" \
  -H "X-auth-access-token: ${TOKEN}"

# Step 3: List access control policies
curl -k "https://YOUR_FMC_IP/api/fmc_config/v1/domain/${DOMAIN}/policy/accesspolicies" \
  -H "X-auth-access-token: ${TOKEN}"

# Step 4: List managed devices
curl -k "https://YOUR_FMC_IP/api/fmc_config/v1/domain/${DOMAIN}/devices/devicerecords" \
  -H "X-auth-access-token: ${TOKEN}"
```

### FMC API Explorer

Cisco FMC includes a built-in Swagger UI at:
```
https://YOUR_FMC_IP/api/api-explorer
```
Use this to explore and test all available endpoints directly from your browser.

## References

- **FMC REST API Quick Start Guide**: [Cisco Documentation](https://www.cisco.com/c/en/us/td/docs/security/firepower/770/API/REST/secure_firewall_management_center_rest_api_quick_start_guide_770/Objects_In_The_REST_API.html)
- **FMC API Explorer**: `https://YOUR_FMC_IP/api/api-explorer`
- **OpenAPI Spec**: `openapi_specs/fmc_oas3.json`

---

**Last Updated**: April 2026
**Status**: Active documentation
