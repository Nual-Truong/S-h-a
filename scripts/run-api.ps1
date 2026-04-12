Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. .\.venv\Scripts\Activate.ps1
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
