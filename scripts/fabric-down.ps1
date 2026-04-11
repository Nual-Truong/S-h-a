Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Push-Location fabric/network
try {
    .\scripts\network-down.ps1
}
finally {
    Pop-Location
}
