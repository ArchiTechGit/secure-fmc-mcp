# Available Operations - Cisco FMC REST API

**Total Operations**: 1,331+
**Spec File**: `openapi_specs/fmc_oas3.json`
**Status**: All operations available as MCP tools

## Operation Summary by Tag

| Tag | Operations | Description |
|-----|-----------|-------------|
| Object | 508 | Network objects, host groups, ports, URLs, geolocation |
| Policy | 328 | Access control, NAT, intrusion, file, DNS policies |
| Devices | 227 | Managed devices, HA pairs, VTIs, physical/virtual interfaces |
| Chassis | 43 | Firepower chassis and security module management |
| Integration | 30 | Cloud, SD-WAN, and third-party integrations |
| Templates | 29 | Device configuration templates |
| Intelligence | 21 | Threat intelligence feeds |
| Troubleshoot | 18 | Packet tracer, captures, health checks |
| Device HA Pairs | 13 | High-availability pair management |
| Deployment | 11 | Deploy pending changes to devices |
| Health | 11 | Health policy and monitoring |
| Network Map | 10 | Discovered network topology |
| Backup | 9 | Backup and restore |
| Device Clusters | 9 | Clustering configuration |
| Users | 9 | FMC user management |
| Updates | 8 | Software and intrusion rule updates |
| Analysis | 6 | Active sessions, identified users, user activity |
| Change Management | 6 | Audit trail and change records |
| License | 6 | Smart license management |
| System Configuration | 6 | System settings |

## Access Control by HTTP Method

| Method | Access |
|--------|--------|
| GET | ✅ Always Available (Read-Only) |
| POST | 🔒 Requires Edit Mode |
| PUT | 🔒 Requires Edit Mode |
| DELETE | 🔒 Requires Edit Mode |

## Key Operation Categories

### Object Management
The largest category — covers all reusable objects referenced in policies:

| Object Type | Example Operations |
|-------------|-------------------|
| Network Objects | `getAllNetworkObjects`, `createNetworkObjects`, `getNetworkObject` |
| Host Groups | `getAllHostGroupObjects`, `createHostGroupObjects` |
| Port Objects | `getAllProtocolPortObjects`, `createProtocolPortObjects` |
| URL Objects | `getAllURLObjects`, `createURLObjects` |
| FQDN Objects | `getAllFQDNObjects`, `createFQDNObjects` |
| Geolocation | `getAllGeoLocations` |
| Security Zones | `getAllSecurityZoneObjects`, `createSecurityZoneObjects` |
| Variable Sets | `getAllVariableSets` |
| VPN Topologies | `getAllVpnTopologies`, `createVpnTopology` |
| Sinkhole Objects | `getAllSinkholeObjects` |

**Tool name format**: `fmc_<operationId>`

**Example**: `fmc_getAllNetworkObjects`

### Policy Management
Covers all firewall policy types:

| Policy Type | Example Operations |
|-------------|-------------------|
| Access Control | `getAllAccessPolicies`, `createAccessPolicy`, `getAccessPolicy` |
| NAT | `getAllFTDNatPolicies`, `createFTDNatPolicy` |
| Intrusion | `getAllIntrusionPolicies` |
| File Policies | `getAllFilePolicies` |
| DNS Policies | `getAllDNSPolicies` |
| Identity Policies | `getAllIdentityPolicies` |
| SSL Policies | `getAllSSLPolicies` |
| QoS Policies | `getAllQosPolicies` |
| Prefilter Policies | `getAllPrefilterPolicies` |
| Routing | `getAllIPv4StaticRoutes`, `createIPv4StaticRoute` |

### Device Management
Manage the devices controlled by FMC:

| Area | Example Operations |
|------|-------------------|
| Device Records | `getAllDevices`, `registerDevice`, `getDevice`, `deleteDevice` |
| Interfaces | `getAllFTDPhysicalInterfaces`, `getAllBridgeGroupInterfaces` |
| HA Pairs | `getAllFTDHAPairs`, `createFTDHAPair`, `deleteHAPair` |
| VTIs | `getAllVTIInterfaces`, `createVTIInterface` |
| Inline Sets | `getAllInlineSets` |

### Deployment
Deploy pending configuration changes to devices:

| Operation | Description |
|-----------|-------------|
| `createDeploymentRequest` | Deploy changes to one or more devices |
| `getAllDeployableDevices` | List devices with pending changes |
| `getJobStatus` | Check deployment job status |
| `getAllDeploymentRequests` | List recent deployments |

## Usage Examples

### Example 1: List all network objects
```
"Show me all network objects defined in FMC"
```
Uses: `fmc_getAllNetworkObjects` (GET /api/fmc_config/v1/domain/{domainUUID}/object/networks)

### Example 2: Get access control policies
```
"List all access control policies on the FMC"
```
Uses: `fmc_getAllAccessPolicies` (GET /api/fmc_config/v1/domain/{domainUUID}/policy/accesspolicies)

### Example 3: List managed devices
```
"Which devices are managed by this FMC?"
```
Uses: `fmc_getAllDevices` (GET /api/fmc_config/v1/domain/{domainUUID}/devices/devicerecords)

### Example 4: Check pending deployments
```
"Which devices have pending configuration changes?"
```
Uses: `fmc_getAllDeployableDevices` (GET /api/fmc_config/v1/domain/{domainUUID}/deployment/deployabledevices)

### Example 5: Get intrusion policies
```
"Show me the intrusion prevention policies"
```
Uses: `fmc_getAllIntrusionPolicies` (GET /api/fmc_config/v1/domain/{domainUUID}/policy/intrusionpolicies)

## Tool Name Format

All operations are exposed as MCP tools with the naming format:
- **Format**: `fmc_{operationId}`
- **Example**: `fmc_getAllNetworkObjects`
- **Truncation**: If name exceeds 64 chars, uses just `{operationId}` truncated to 64

## The `domainUUID` Parameter

Most FMC config operations require `domainUUID` as a path parameter. This is the UUID of the administrative domain you want to work in. The correct value is returned in the `DOMAIN_UUID` header when you authenticate.

If you have multiple domains configured, use `GET /api/fmc_platform/v1/info/domain` to list all available domains and their UUIDs.

## Read-Only vs Edit Mode

### Read-Only Mode (Default)
- ✅ All **GET** operations available
- ❌ POST/PUT/DELETE operations blocked
- Returns permission error with edit mode requirement

### Edit Mode (EDIT_MODE_ENABLED=true or enabled via Web UI)
- ✅ All **GET** operations available
- ✅ All **POST** operations available
- ✅ All **PUT** operations available
- ✅ All **DELETE** operations available

## List All Operations

To dump all operations from the spec:

```bash
docker exec -i fmc_mcp_mcp_server python -c "
import sys
sys.path.insert(0, '/app')
from src.core.api_loader import APILoader

loader = APILoader()
spec = loader.load_openapi_spec('fmc_oas3.json')
operations = loader.list_operations(spec)

for op in sorted(operations, key=lambda x: x['tags'][0] if x['tags'] else ''):
    tag = op['tags'][0] if op['tags'] else 'untagged'
    print(f\"{op['method']:6s} {tag:20s} {op['operation_id']}\")
" 2>/dev/null
```

## API Documentation

For detailed information about each operation:
- **OpenAPI Spec**: `openapi_specs/fmc_oas3.json`
- **Cisco FMC API Explorer**: `https://YOUR_FMC_IP/api/api-explorer`
- **Cisco Documentation**: https://www.cisco.com/c/en/us/td/docs/security/firepower/770/API/REST/secure_firewall_management_center_rest_api_quick_start_guide_770/Objects_In_The_REST_API.html

---

**Last Updated**: April 2026
**Spec Version**: FMC REST API v7.7
