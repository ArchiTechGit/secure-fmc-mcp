# Claude Desktop Integration Guide

## Overview

This guide explains how to connect Claude Desktop to the Cisco FMC MCP Server, enabling Claude to interact with your Cisco Secure Firewall Management Center.

## Prerequisites

- Cisco FMC MCP Server deployed and running
- Claude Desktop installed
- For remote connections: Node.js 18+ installed locally

## Quick Setup

### Remote Connection (Recommended)

For accessing the MCP server running on a remote host:

**Step 1:** Locate your Claude Desktop configuration file:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

**Step 2:** Add the MCP server configuration:

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

Replace `YOUR_SERVER_IP` with your server's IP address (e.g., `192.168.1.213`).

**Step 3:** Restart Claude Desktop

- macOS: Cmd+Q to quit, then relaunch
- Windows: Close and reopen the application
- Linux: Close and reopen the application

### Local Connection

For Claude Desktop running on the same machine as Docker:

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

## Handling Self-Signed Certificates

Since the MCP server uses self-signed certificates, you may encounter SSL/TLS errors.

### Option 1: Accept Self-Signed Certificates (Development)

Set the environment variable before running Claude Desktop:

**macOS/Linux:**
```bash
export NODE_TLS_REJECT_UNAUTHORIZED=0
open -a "Claude"
```

**Windows (PowerShell):**
```powershell
$env:NODE_TLS_REJECT_UNAUTHORIZED=0
& "C:\Path\To\Claude.exe"
```

### Option 2: Add Certificate to Trust Store (Production)

1. Download the server certificate:
   ```bash
   openssl s_client -connect YOUR_SERVER_IP:8444 -showcerts </dev/null 2>/dev/null | \
     openssl x509 -outform PEM > fmc-mcp.crt
   ```

2. Add to your system's trust store:
   - **macOS:** Double-click the .crt file and add to Keychain Access
   - **Windows:** Right-click > Install Certificate
   - **Linux:** Copy to `/usr/local/share/ca-certificates/` and run `update-ca-certificates`

## Verifying the Connection

After restarting Claude Desktop:

1. Look for the MCP server indicator (hammer icon) in Claude Desktop
2. You should see "cisco-fmc" listed as an available server
3. The indicator should show a green status

### Test Query

Try asking Claude:

```
"List all access control policies on the FMC"
```

or

```
"What devices are currently managed by FMC?"
```

## Available Operations

### Read Operations (Always Available)

- List and get network objects (hosts, networks, ports, URLs)
- View access control, NAT, and intrusion policies
- Query managed device inventory and status
- Get deployment status and pending changes
- View health monitoring data
- Browse VPN topologies

### Write Operations (Requires Edit Mode)

Write operations are disabled by default. To enable:

1. Go to Web UI: `https://YOUR_SERVER_IP:7443`
2. Navigate to **Security** page
3. Enable **Edit Mode**
4. Optionally whitelist specific operations

Once enabled, you can:
- Create and modify network objects
- Update access control rules
- Deploy configuration changes to devices
- Manage NAT and routing policies

## Secure Access with API Token

For additional security, you can require an API token:

**Step 1:** Set the token in your deployment's `.env` file:

```env
MCP_API_TOKEN=your-secure-token-here
```

**Step 2:** Restart the services:

```bash
docker compose down
docker compose up -d
```

**Step 3:** Update Claude Desktop configuration:

```json
{
  "mcpServers": {
    "cisco-fmc": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "https://YOUR_SERVER_IP:8444/mcp/sse",
        "--transport",
        "sse-only",
        "--header",
        "Authorization: Bearer your-secure-token-here"
      ]
    }
  }
}
```

## Troubleshooting

### Server Not Showing Up

1. **Check Docker containers are running:**
   ```bash
   docker compose ps
   ```

2. **Check server logs:**
   ```bash
   docker compose logs -f fmc_mcp_mcp_server
   ```

3. **Verify Claude Desktop config syntax:**
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python -m json.tool
   ```

4. **Test the SSE endpoint:**
   ```bash
   curl -k https://YOUR_SERVER_IP:8444/mcp/sse
   ```

### Permission Errors

- Check edit mode setting in Web UI
- Verify your user has appropriate role assignments
- Review audit logs: `https://YOUR_SERVER_IP:7443/audit`

### Connection Errors

1. **Test network connectivity:**
   ```bash
   curl -k https://YOUR_SERVER_IP:8444/api/health
   ```

2. **Check firewall rules:**
   - Port 8444 must be accessible

3. **Verify SSL certificate:**
   ```bash
   openssl s_client -connect YOUR_SERVER_IP:8444 -servername YOUR_SERVER_IP
   ```

### SSL/Certificate Errors

If you see "self-signed certificate" or "unable to verify" errors:

1. Use `NODE_TLS_REJECT_UNAUTHORIZED=0` for development
2. Add the certificate to your system trust store for production
3. Or use proper CA-signed certificates

## Monitoring Usage

### View Real-Time Logs

```bash
docker compose logs -f fmc_mcp_mcp_server
```

### Audit Log Access

All MCP operations are logged. View them at:
- Web UI: `https://YOUR_SERVER_IP:7443/audit`
- Database:
  ```bash
  docker compose exec fmc_mcp_postgres psql -U mcp_user -d fmc_mcp -c \
    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20;"
  ```

## Example Queries

### Read-Only Examples

```
"Show me all network objects defined in the FMC"

"What access control policies exist on this FMC?"

"List all devices managed by FMC"

"What are the NAT policies configured?"

"Show me the intrusion prevention policies"

"Which devices have pending configuration changes that need to be deployed?"
```

### Write Mode Examples (After Enabling)

```
"Create a new network object for 10.10.10.0/24 named 'Corp-LAN'"

"Add a new host object for 192.168.1.100 named 'Web-Server'"

"Deploy the pending changes to device 'FTD-01'"
```

## Best Practices

1. **Start Read-Only:** Test queries before enabling write mode
2. **Use Specific Names:** Include policy names, device names, and object names in queries
3. **Monitor Logs:** Keep `docker compose logs -f` running during testing
4. **Review Audit:** Check audit logs after operations
5. **Limit Access:** Use API tokens in shared environments
6. **Domain UUID:** Most FMC operations need a `domainUUID` — Claude will prompt for it or you can tell it upfront
