#!/bin/bash

# Cisco FMC MCP Server Setup Script

set -e

echo "======================================"
echo "Cisco FMC MCP Server Setup"
echo "======================================"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker found: $(docker --version)"
echo "✓ Docker Compose found: $(docker-compose --version)"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file with your Cisco FMC credentials"
    echo ""
    echo "Required configuration:"
    echo "  - FMC_HOST_URL: Your FMC URL (e.g. https://192.168.1.1)"
    echo "  - FMC_USERNAME: Your FMC admin username"
    echo "  - FMC_PASSWORD: Your FMC admin password"
    echo "  - ENCRYPTION_KEY: Generate with the command below"
    echo ""
    echo "Generate encryption key:"
    echo "  python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo ""
    read -p "Press Enter after editing .env file..."
else
    echo "✓ .env file exists"
fi

# Validate .env has required variables
echo ""
echo "Validating configuration..."

source .env

if [ -z "$FMC_HOST_URL" ]; then
    echo "⚠️  FMC_HOST_URL is not set in .env"
fi

if [ -z "$FMC_USERNAME" ]; then
    echo "⚠️  FMC_USERNAME is not set in .env"
fi

if [ -z "$FMC_PASSWORD" ]; then
    echo "⚠️  FMC_PASSWORD is not set in .env"
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "⚠️  ENCRYPTION_KEY is not set in .env"
    echo "Generate with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
fi

echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 1
fi

# Validate external Docker network required by docker-compose.yml
echo ""
echo "Checking external Docker network..."
bash scripts/preflight-network.sh

# Build and start services
echo ""
echo "Building Docker images..."
docker-compose build

echo ""
echo "Starting services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "Checking service status..."
docker-compose ps

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. View logs: docker-compose logs -f"
echo "  2. Check database: docker-compose exec fmc_mcp_postgres psql -U mcp_user -d fmc_mcp"
echo "  3. Configure Claude Desktop with MCP server"
echo ""
echo "Useful commands:"
echo "  - Stop services: docker-compose stop"
echo "  - Start services: docker-compose start"
echo "  - View logs: docker-compose logs -f fmc_mcp_mcp_server"
echo "  - Restart: docker-compose restart fmc_mcp_mcp_server"
echo ""
echo "Documentation: ./docs/"
echo ""
