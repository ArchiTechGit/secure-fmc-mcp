# Cisco FMC MCP Server

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](requirements.txt)
[![Next.js](https://img.shields.io/badge/Next.js-16.0-black?logo=next.js&logoColor=white)](web-ui/package.json)

A comprehensive Model Context Protocol (MCP) server for Cisco Secure Firewall Management Center (FMC), enabling AI agents like Claude to interact with FMC REST APIs for intelligent firewall automation and management.

## Features

### Core Capabilities
- **Complete API Coverage**: Access to 1,331+ operations across the full FMC REST API
  - Object API (508 operations): Network objects, host groups, ports, URLs, geolocation
  - Policy API (328 operations): Access control, NAT, intrusion, file, DNS policies
  - Devices API (227 operations): Managed devices, HA pairs, device clusters
  - Chassis API (43 operations): Firepower chassis management
  - Integration, Health, Deployment, Backup, Users, and more

- **Security First**:
  - HTTPS with self-signed certificates (auto-generated)
  - Multi-user authentication with role-based access control (RBAC)
  - Read-only mode by default with explicit edit mode enablement
  - Fernet-encrypted credential storage
  - Complete audit logging with client IP tracking
  - Granular operation whitelisting per role

- **Web Management UI**:
  - Next.js-based management interface with HTTPS
  - User and role management
  - Real-time system health monitoring
  - Audit log viewer with CSV export
  - FMC device management with connection testing
  - Security configuration dashboard
  - API guidance and workflow management

- **Enterprise Ready**:
  - PostgreSQL database for persistence
  - Docker-based deployment on an external bridge network
  - Complete audit trail for compliance
  - LDAP integration support

## Quick Start

### Prerequisites

- **Docker** 20.10+ and Docker Compose 2.0+
- **Cisco Secure Firewall Management Center** 7.x
- **Node.js** 18+ (for remote MCP access via mcp-remote)

### 1. Clone and Configure

```bash
git clone https://github.com/ArchiTechGit/secure-fmc-mcp.git
cd secure-fmc-mcp

# Create environment file with your server's IP address
echo "CERT_SERVER_IP=YOUR_SERVER_IP" > .env
```

Replace `YOUR_SERVER_IP` with your server's actual IP address (e.g., `192.168.1.213`).

### 2. Start Services

```bash
bash scripts/preflight-network.sh
docker compose up -d --build
```

This will:
- Generate self-signed SSL certificates automatically
- Start PostgreSQL database (port 15434)
- Start Web API with HTTPS (port 8446)
- Start Web UI with HTTPS (port 7445)
- Start MCP Server for Claude integration

### 3. Initial Setup

1. Open your browser and navigate to:
   ```
   https://YOUR_SERVER_IP:7445
   ```

2. Accept the self-signed certificate warning

3. Complete the initial admin setup:
   - Username: `admin`
   - Email: `admin@example.com`
   - Password: `Admin123!` (or your preferred password)

4. Configure your first FMC device:
   - Navigate to **Clusters** page
   - Click "Add New Cluster"
   - Enter your FMC details (URL, username, password)
   - Click "Test Connection" to verify
   - Save the device configuration

### 4. Configure Claude Desktop

Add to your Claude Desktop configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

#### Remote Deployment (Recommended)

```json
{
  "mcpServers": {
    "cisco-fmc": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "https://YOUR_SERVER_IP:8446/mcp/sse",
        "--transport",
        "sse-only"
      ]
    }
  }
}
```

Replace `YOUR_SERVER_IP` with your server's IP address.

> **Note:** Since we use self-signed certificates, you may need to set `NODE_TLS_REJECT_UNAUTHORIZED=0` in your environment or accept the certificate in your system's trust store.

#### Local Deployment (same machine as Docker)

```json
{
  "mcpServers": {
    "cisco-fmc": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "fmc_mcp_mcp_server",
        "python",
        "src/main.py"
      ]
    }
  }
}
```

Restart Claude Desktop, and you'll see the Cisco FMC tools available!

## Architecture

```
                      External Clients
                  (Browser, Claude Desktop)
                           |
                    [HTTPS/TLS]
                           |
           +---------------+---------------+
           |                               |
      Port 7445                       Port 8446
           |                               |
+----------+----------+    +---------------+--------------+
|       Web UI        |    |           Web API            |
|      (Next.js)      |--->|          (FastAPI)           |
|      HTTPS Proxy    |    |  +----------+  +---------+   |
+---------------------+    |  | REST API |  | MCP SSE |   |
                           |  +----------+  +---------+   |
                           +---------------+--------------+
                                           |
                    +----------------------+----------------------+
                    |                      |                      |
           +--------+--------+    +--------+--------+    +--------+--------+
           |   PostgreSQL    |    |   MCP Server    |    |  Cisco FMC      |
           |   Port 15434    |    |   (stdio)       |    |  Devices        |
           +-----------------+    +-----------------+    +-----------------+

Certificate Volume: /app/certs/ (auto-generated on first startup)
```

## Port Summary

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Web UI | 7445 | HTTPS | Management interface |
| Web API | 8446 | HTTPS | REST API and MCP SSE endpoint |
| PostgreSQL | 15434 | TCP | Database (mapped from 5432) |
| Internal HTTP | 7102 | HTTP | Internal proxy communication |

## Environment Variables

### Required for Production

Create a `.env` file with:

```env
# Your server's IP address (for SSL certificate SAN)
CERT_SERVER_IP=192.168.1.213

# Security (generate unique keys for production)
ENCRYPTION_KEY=your-unique-fernet-key
SESSION_SECRET_KEY=your-random-secret-key

# External Docker network (must already exist)
DOCKER_EXTERNAL_NETWORK=fmc-mcp-cluster

# FMC device credentials (can also be configured via Web UI)
FMC_HOST_URL=https://192.168.1.1
FMC_USERNAME=admin
FMC_PASSWORD=YourPassword
FMC_VERIFY_SSL=false
```

**Generate Encryption Key:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Optional Variables

```env
# SSL Certificate Configuration
CERT_DAYS=365                    # Certificate validity (default: 365)
CERT_CN=fmc-mcp                  # Certificate common name

# Security
EDIT_MODE_ENABLED=false          # Enable write operations
MCP_API_TOKEN=your-token         # Optional: Require token for MCP access

# Logging
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
```

## Security

### HTTPS Configuration

Self-signed certificates are automatically generated on first startup:
- Stored in Docker volume `fmc-mcp-certs`
- Valid for 365 days (configurable via `CERT_DAYS`)
- Includes localhost, 127.0.0.1, and your server IP in SAN

To regenerate certificates:
```bash
docker volume rm fmc-mcp-certs
docker compose up -d
```

### Multi-User RBAC

The platform supports multiple users with role-based access control:

- **Admin Role**: Full access to all operations
- **Operator Role**: Read access + specific write operations
- **Viewer Role**: Read-only access

Users can be managed through the Web UI under **Security > Users**.

### Best Practices

1. **Change default admin password** after initial setup
2. **Keep `EDIT_MODE_ENABLED=false`** unless write operations are needed
3. **Use strong encryption keys** for production
4. **Review audit logs** regularly for unauthorized activity
5. **Limit network access** to the server

## Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get up and running in 5 minutes
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and components
- **[User Guide](docs/USER_GUIDE.md)** - Comprehensive usage documentation
- **[Web UI Guide](docs/WEB_UI_GUIDE.md)** - Managing the system via web interface
- **[Claude Desktop Setup](docs/CLAUDE_DESKTOP_SETUP.md)** - Detailed Claude integration
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment recommendations
- **[Multi-User RBAC](docs/MULTI_USER_RBAC.md)** - Role-based access control
- **[API Guidance System](docs/API_GUIDANCE_SYSTEM.md)** - Customizing API behavior

## Troubleshooting

### Check Container Status
```bash
docker compose ps
docker compose logs -f
```

### Certificate Issues
```bash
# View certificate details
docker compose exec fmc_mcp_web_api openssl x509 -in /app/certs/server.crt -text -noout

# Regenerate certificates
docker volume rm fmc-mcp-certs
docker compose up -d
```

### Database Issues
```bash
# Connect to database
docker compose exec fmc_mcp_postgres psql -U mcp_user -d fmc_mcp

# Check tables
\dt

# View audit logs
SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10;
```

### Network Connectivity
```bash
# Test API endpoint
curl -k https://localhost:8446/api/health

# Test Web UI
curl -k https://localhost:7445
```

## Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/ArchiTechGit/secure-fmc-mcp.git
cd secure-fmc-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start database only
docker compose up fmc_mcp_postgres -d

# Run API locally
python src/api/web_api.py

# Run Web UI in dev mode
cd web-ui
npm install
npm run dev
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Anthropic** - For the Claude AI platform and MCP protocol
- **Cisco** - For the FMC REST API
- **FastMCP** - For the excellent MCP framework

---

**Made with care for firewall automation**
