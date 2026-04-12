#!/bin/bash
# Verify that the configured external Docker network exists before startup.

set -euo pipefail

NETWORK_NAME="openshell-cluster-nemoclaw"

# Load .env if present so DOCKER_EXTERNAL_NETWORK can override the default.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

NETWORK_NAME="${DOCKER_EXTERNAL_NETWORK:-$NETWORK_NAME}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

if docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "OK: External Docker network exists: $NETWORK_NAME"
    exit 0
fi

echo "Error: Required external Docker network not found: $NETWORK_NAME"
echo "Create it with:"
echo "  docker network create --driver bridge $NETWORK_NAME"
echo ""
echo "If you use a different existing network, set DOCKER_EXTERNAL_NETWORK in .env."
exit 1
