Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NetworkDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $NetworkDir

docker compose up -d
Write-Host "Fabric containers are up."
