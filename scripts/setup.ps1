Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.venv')) {
    Write-Host 'Creating virtual environment...'
    python -m venv .venv
}

Write-Host 'Activating virtual environment...'
. .\.venv\Scripts\Activate.ps1

Write-Host 'Installing Python dependencies...'
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host 'Setup completed.'
