import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _unquote(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


for candidate in (Path.cwd() / ".env", PROJECT_ROOT / ".env"):
    _load_env_file(candidate)

DB_CONFIG = {
    "host": "localhost",
    "database": "sfm",
    "user": "postgres",
    "password": "123456",
}

# App mode: fabric-first | hybrid | legacy
APP_MODE = os.getenv("APP_MODE", "fabric-first").strip().lower()

# Legacy local blockchain should be off by default in fabric-first mode.
ENABLE_LEGACY_BLOCKCHAIN = APP_MODE in {"legacy", "hybrid"}

# Optional auto sync toggle for ETL -> Fabric client.
FABRIC_AUTO_SYNC = os.getenv("FABRIC_AUTO_SYNC", "1").strip() != "0"

# Fabric hash mode: total | per-transaction | both
FABRIC_HASH_MODE = os.getenv("FABRIC_HASH_MODE", "total").strip().lower()
if FABRIC_HASH_MODE not in {"total", "per-transaction", "both"}:
    FABRIC_HASH_MODE = "total"

# Dashboard access control: leave empty to allow everyone; set to require admin password.
DASHBOARD_ADMIN_PASSWORD = os.getenv("DASHBOARD_ADMIN_PASSWORD", "").strip()

# Optional viewer label for dashboard context.
DASHBOARD_VIEWER_LABEL = os.getenv("DASHBOARD_VIEWER_LABEL", "viewer").strip() or "viewer"