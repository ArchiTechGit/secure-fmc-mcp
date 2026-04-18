# Cisco FMC MCP Server - Quick Start Guide

Get up and running in 5 minutes!

## What You Get

A complete Cisco FMC management system with:
- **MCP Server**: 1,331+ operations across the full FMC REST API (Object, Policy, Devices, and more)
- **Web API**: FastAPI REST backend with HTTPS
- **Web UI**: Next.js/React dashboard with authentication
- **PostgreSQL**: Database with encrypted credentials and audit logging
- **HTTPS**: Self-signed certificates auto-generated

## Quick Start

### Step 1: Clone and Configure

```bash
git clone https://github.com/ArchiTechGit/secure-fmc-mcp.git
cd secure-fmc-mcp

# Configure your server's IP address
echo "CERT_SERVER_IP=YOUR_SERVER_IP" > .env
```

Replace `YOUR_SERVER_IP` with your server's IP address (e.g., `192.168.1.213`).

If you need to use an existing Docker bridge network, add this to `.env`:

```bash
echo "DOCKER_EXTERNAL_NETWORK=fmc-mcp-cluster" >> .env
```

Make sure that network already exists:

```bash
docker network create --driver bridge fmc-mcp-cluster
```

### Step 2: Start Services

```bash
bash scripts/preflight-network.sh
docker compose up -d --build
```

Wait for all services to start (about 1-2 minutes on first run).

### Step 3: Access Web UI

1. Open browser: `https://YOUR_SERVER_IP:7443`
2. Accept the self-signed certificate warning
3. Create admin account:
   - Username: `admin`
   - Email: `admin@example.com`
   - Password: `Admin123!`

### Step 4: Add Your FMC Device

1. Navigate to **Clusters** page
2. Click **Add New Cluster**
3. Enter details:
   - Name: `my-fmc` (friendly name)
   - URL: `https://192.168.1.1` (your FMC IP or hostname)
   - Username: `admin`
   - Password: Your FMC password
   - SSL Verification: Off (for self-signed certs)
4. Click **Test Connection** to verify
5. Click **Create Cluster**

### Step 5: Configure Claude Desktop

Add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cisco-fmc": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "https://YOUR_SERVER_IP:8444/mcp/sse",
        "--transport",
        "sse-only"
      ]
    }
  }
}
```

Restart Claude Desktop and try: "List all access control policies on the FMC"

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | `https://YOUR_SERVER_IP:7443` | Management dashboard |
| Web API | `https://YOUR_SERVER_IP:8444` | REST API |
| API Docs | `https://YOUR_SERVER_IP:8444/docs` | Swagger documentation |
| MCP SSE | `https://YOUR_SERVER_IP:8444/mcp/sse` | Claude Desktop endpoint |

## Common Commands

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop everything
docker compose down

# Clean restart (keeps data)
docker compose down && docker compose up -d

# Full reset (WARNING: deletes all data!)
docker compose down -v
docker volume rm fmc-mcp-certs
docker compose up -d --build
```

## Troubleshooting

### Can't access Web UI
```bash
# Check containers are running
docker compose ps

# Check for errors
docker compose logs fmc_mcp_web_ui
docker compose logs fmc_mcp_web_api
```

### Certificate issues
```bash
# Regenerate certificates
docker volume rm fmc-mcp-certs
docker compose up -d
```

### Database issues
```bash
# Connect to database
docker compose exec fmc_mcp_postgres psql -U mcp_user -d fmc_mcp

# Check tables
\dt
```

### Test FMC connection manually
```bash
# Get an auth token from FMC
curl -k -X POST https://YOUR_FMC_IP/api/fmc_platform/v1/auth/generatetoken \
  -u admin:password \
  -H "Content-Type: application/json"
# Look for X-auth-access-token in the response headers
```

## Next Steps

1. **Add more FMC devices**: Configure additional FMC instances
2. **Set up users**: Add team members with role-based access
3. **Enable edit mode**: Allow write operations when needed
4. **Review audit logs**: Monitor all API operations
5. **Read the docs**: Check `docs/` folder for detailed guides

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Production setup
- [Claude Desktop Setup](docs/CLAUDE_DESKTOP_SETUP.md) - MCP integration
- [Multi-User RBAC](docs/MULTI_USER_RBAC.md) - User management
- [API Guidance](docs/API_GUIDANCE_SYSTEM.md) - Customizing API behavior

---

**Ready to use!**
