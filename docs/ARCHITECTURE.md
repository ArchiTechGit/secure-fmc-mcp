# Architecture Documentation

## Overview

The Cisco FMC MCP Server is built with a modular, layered architecture designed for security, maintainability, and extensibility.

## Core Components

### 1. MCP Server Core (`src/core/`)

**Purpose**: Handles MCP protocol communication and tool registration

**Key Files**:
- `mcp_server.py`: Main MCP server implementation (`FMCMCPServer`)
- `api_loader.py`: OpenAPI specification loader and validator
- `api_registry.py`: FMC API definition registry

**Responsibilities**:
- Load and validate the FMC OpenAPI specification
- Generate MCP tools from API operations
- Handle tool execution requests
- Manage stdio communication

### 2. Middleware Layer (`src/middleware/`)

**Purpose**: Cross-cutting concerns for all API operations

#### Authentication Middleware (`auth.py`)
- Manages FMC token-based authentication
- Handles access/refresh token lifecycle
- Executes authenticated API requests
- Automatic token refresh on 401 responses

#### Security Middleware (`security.py`)
- Enforces read-only vs edit mode
- Blocks write operations when edit mode disabled
- Validates operation permissions
- Provides security status reporting

#### Audit Logger (`logging.py`)
- Logs all operations to PostgreSQL
- Tracks request/response data
- Records successes and failures
- Provides audit query capabilities

### 3. Services Layer (`src/services/`)

**Purpose**: Business logic and external integrations

#### Credential Manager (`credential_manager.py`)
- Secure credential storage with Fernet encryption
- CRUD operations for FMC device credentials
- Credential retrieval and decryption

#### FMC API Client (`fmc_api.py`)
- HTTP client for the Cisco FMC REST API
- Token generation via `/api/fmc_platform/v1/auth/generatetoken`
- Access token refresh and revocation
- Retry logic and error handling

### 4. Data Layer (`src/models/`)

**Purpose**: Database models using SQLAlchemy ORM

**Models**:
- `Cluster`: FMC device connection credentials
- `SecurityConfig`: Global security settings
- `APIEndpoint`: Registry of available API operations
- `AuditLog`: Audit trail of all operations

### 5. Configuration (`src/config/`)

**Purpose**: Application configuration and database setup

**Components**:
- `settings.py`: Pydantic settings from environment (`FMC_HOST_URL`, `FMC_USERNAME`, etc.)
- `database.py`: SQLAlchemy async engine setup
- `schema.sql`: PostgreSQL schema definition

## Data Flow

### Read Operation (GET)

```
1. User Query → Claude Desktop
2. Claude Desktop → MCP Server (tool call)
3. MCP Server → Security Middleware (check: always allowed)
4. MCP Server → Auth Middleware (authenticate/refresh token if needed)
5. Auth Middleware → FMC REST API
6. FMC → Response
7. MCP Server → Audit Logger (log success)
8. MCP Server → Claude Desktop (return data)
```

### Write Operation (POST/PUT/DELETE)

```
1. User Query → Claude Desktop
2. Claude Desktop → MCP Server (tool call)
3. MCP Server → Security Middleware (check edit mode)
   ├─ If disabled → PermissionError → User
   └─ If enabled → Continue
4. MCP Server → Auth Middleware
5. Auth Middleware → FMC REST API
6. FMC → Response
7. MCP Server → Audit Logger (log with request body)
8. MCP Server → Claude Desktop (return result)
```

## Security Architecture

### Defense in Depth

1. **Network Layer**: Docker network isolation
2. **Application Layer**: Read-only mode enforcement
3. **Data Layer**: Encrypted credentials at rest
4. **Audit Layer**: Complete operation logging

### FMC Authentication Flow

```
┌─────────────┐
│ MCP Server  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Auth Middleware │
└──────┬──────────┘
       │
       ▼
┌─────────────────────┐
│ Credential Manager  │
│ (decrypt password)  │
└──────┬──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ FMC API Client                       │
│ POST /api/fmc_platform/v1/auth/      │
│      generatetoken  (Basic Auth)     │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ FMC returns response headers:        │
│  X-auth-access-token                 │
│  X-auth-refresh-token                │
│  DOMAIN_UUID  ← used in API paths   │
│  global_DOMAIN_UUID                  │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Cache tokens                         │
│ Use X-auth-access-token header       │
│ for all subsequent requests          │
└──────────────────────────────────────┘
```

### Encryption

**Credentials Encryption**:
- Algorithm: Fernet (symmetric encryption)
- Key: Environment variable `ENCRYPTION_KEY`
- Scope: Passwords in `clusters` table

**In Transit**:
- HTTPS for FMC communication
- Option to disable SSL verification for dev/test

## Database Schema

### Entity Relationship Diagram

```
┌──────────────┐
│   clusters   │
│──────────────│
│ id (PK)      │◄────┐
│ name (UK)    │     │
│ url          │     │
│ username     │     │
│ password_enc │     │
│ verify_ssl   │     │
│ is_active    │     │
└──────────────┘     │
                     │
                     │ cluster_id (FK)
                     │
┌──────────────┐     │
│  audit_log   │     │
│──────────────│     │
│ id (PK)      │     │
│ cluster_id   │─────┘
│ operation_id │
│ http_method  │
│ path         │
│ request_body │
│ response_*   │
│ error_msg    │
│ timestamp    │
└──────────────┘

┌──────────────────┐
│ security_config  │
│──────────────────│
│ id (PK)          │
│ edit_mode_enabled│
│ allowed_ops[]    │
│ audit_logging    │
└──────────────────┘

┌──────────────────┐
│  api_endpoints   │
│──────────────────│
│ id (PK)          │
│ api_name         │
│ operation_id (UK)│
│ http_method      │
│ path             │
│ enabled          │
│ requires_edit    │
└──────────────────┘
```

## Tool Generation

### From OpenAPI to MCP Tool

```python
# FMC OpenAPI Operation
{
  "get": {
    "operationId": "getAllNetworkObjects",
    "summary": "Get all network objects",
    "parameters": [
      {"name": "domainUUID", "in": "path", "required": true},
      {"name": "limit", "in": "query", "schema": {"type": "integer"}}
    ]
  }
}

# Generated MCP Tool
Tool(
  name="fmc_getAllNetworkObjects",
  description="Get all network objects\nEndpoint: GET /api/fmc_config/v1/domain/{domainUUID}/object/networks\nAPI: Fmc",
  inputSchema={
    "type": "object",
    "properties": {
      "domainUUID": {"type": "string", "description": "Path parameter: domainUUID"},
      "limit": {"type": "integer", "description": "Query parameter: limit"}
    },
    "required": ["domainUUID"]
  }
)
```

## FMC API Structure

The FMC REST API is split into two roots, both covered by `fmc_oas3.json`:

| Root | Purpose | Example paths |
|------|---------|---------------|
| `/api/fmc_config/v1/domain/{domainUUID}/...` | Configuration objects, policy, devices | `/object/networks`, `/policy/accesspolicies`, `/devices/devicerecords` |
| `/api/fmc_platform/v1/...` | Authentication, system info, HA, licensing | `/auth/generatetoken`, `/info/serverversion` |

Most operations require `domainUUID` as a path parameter. The correct UUID is returned in the `DOMAIN_UUID` response header when generating an auth token.

## Extension Points

### Adding Custom Guidance

1. Use the Web UI Guidance section, or
2. Use the `GuidanceService` API:
   ```python
   await service.upsert_api_guidance(
       api_name="fmc",
       display_name="Cisco FMC API",
       general_guidance="Always retrieve domainUUID before making config calls",
       is_active=True
   )
   ```

### Custom Middleware

Implement middleware interface:
```python
class CustomMiddleware:
    async def before_request(self, method, path, params, body):
        pass

    async def after_request(self, response):
        pass
```

## Performance Considerations

### Database Connection Pooling

- Async connection pool (max 10, overflow 20)
- Pre-ping to detect stale connections
- Automatic reconnection on failure

### HTTP Client

- Connection reuse via httpx AsyncClient
- Configurable timeout (default 30s)
- Retry logic (max 3 attempts)
- Automatic token refresh on 401

## Scalability

### Current

- Single MCP server instance
- Single PostgreSQL instance
- Suitable for: Development, small teams

### Future

- Multiple MCP server instances (horizontal scaling)
- PostgreSQL replication
- Redis cluster for caching
- Load balancer for API requests
- Suitable for: Enterprise, large teams

## Error Handling

### Error Propagation

```
API Error
  ↓
Auth/Service Layer (log, wrap)
  ↓
Middleware (audit log)
  ↓
MCP Server (format for MCP protocol)
  ↓
Claude Desktop (user-friendly message)
```

### Error Categories

1. **Authentication Errors**: 401, token expired, credential issues
2. **Permission Errors**: Edit mode required
3. **Validation Errors**: Invalid parameters, missing domainUUID
4. **API Errors**: FMC errors (4xx, 5xx)
5. **System Errors**: Database, network failures

## Logging Strategy

### Log Levels

- **DEBUG**: Detailed trace for development
- **INFO**: Normal operations, successful requests
- **WARNING**: Degraded state, retries, token refreshes
- **ERROR**: Failures that don't stop execution
- **CRITICAL**: Fatal errors requiring intervention

### Log Destinations

1. **stderr**: Real-time application logs
2. **PostgreSQL**: Audit trail (via audit_log table)
3. **Future**: External log aggregation (ELK, Splunk)

## Testing Strategy

### Unit Tests (`tests/unit/`)

- Individual functions and classes
- Mocked dependencies
- Fast execution

### Integration Tests (`tests/integration/`)

- Multi-component workflows
- Real database (test DB)
- Mocked FMC API

### E2E Tests (Future)

- Full stack testing
- Real FMC (sandbox/dev)
- User workflow validation
