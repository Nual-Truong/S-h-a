#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NETWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$NETWORK_DIR"

docker compose up -d

echo "Fabric containers are up."
echo "Next step: use cli container to create and join channel with generated artifacts."
