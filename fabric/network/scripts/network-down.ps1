Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NetworkDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $NetworkDir

docker compose down -v --remove-orphans
Write-Host "Fabric network is down."
