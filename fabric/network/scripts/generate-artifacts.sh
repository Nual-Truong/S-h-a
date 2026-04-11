#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NETWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$NETWORK_DIR"

mkdir -p channel-artifacts
mkdir -p crypto

if ! command -v cryptogen >/dev/null 2>&1; then
  echo "cryptogen not found. Install Hyperledger Fabric binaries first."
  exit 1
fi

if ! command -v configtxgen >/dev/null 2>&1; then
  echo "configtxgen not found. Install Hyperledger Fabric binaries first."
  exit 1
fi

echo "Generating crypto material..."
cryptogen generate --config=./crypto-config.yaml --output=./crypto

echo "Generating genesis block..."
configtxgen -profile FabricOrdererGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block

echo "Generating channel transaction..."
configtxgen -profile FinancialChannel -channelID financialchannel -outputCreateChannelTx ./channel-artifacts/financialchannel.tx

echo "Generating anchor peer update..."
configtxgen -profile FinancialChannel -channelID financialchannel -asOrg Org1MSP -outputAnchorPeersUpdate ./channel-artifacts/Org1MSPanchors.tx

echo "Done. Artifacts generated in ./crypto and ./channel-artifacts"
