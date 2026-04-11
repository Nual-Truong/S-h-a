Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NetworkDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $NetworkDir

# Add Fabric bin to PATH if available
$FabricBin = "$HOME\fabric-binaries\bin"
if (Test-Path $FabricBin) {
    $env:PATH = "$FabricBin;" + $env:PATH
}

if (-not (Get-Command cryptogen -ErrorAction SilentlyContinue)) {
    throw "cryptogen not found. Install Hyperledger Fabric binaries first."
}

if (-not (Get-Command configtxgen -ErrorAction SilentlyContinue)) {
    throw "configtxgen not found. Install Hyperledger Fabric binaries first."
}

New-Item -ItemType Directory -Force -Path "channel-artifacts" | Out-Null
New-Item -ItemType Directory -Force -Path "crypto" | Out-Null

cryptogen generate --config=./crypto-config.yaml --output=./crypto
configtxgen -profile FabricOrdererGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block
configtxgen -profile FinancialChannel -channelID financialchannel -outputCreateChannelTx ./channel-artifacts/financialchannel.tx
configtxgen -profile FinancialChannel -channelID financialchannel -asOrg Org1MSP -outputAnchorPeersUpdate ./channel-artifacts/Org1MSPanchors.tx

Write-Host "Done. Artifacts generated in ./crypto and ./channel-artifacts"
