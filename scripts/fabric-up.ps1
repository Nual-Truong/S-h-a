Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Push-Location fabric/network
try {
    .\scripts\generate-artifacts.ps1
    .\scripts\network-up.ps1
}
finally {
    Pop-Location
}
