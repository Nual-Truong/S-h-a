#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NETWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$NETWORK_DIR"

docker compose down -v --remove-orphans

echo "Fabric network is down."
