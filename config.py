import os

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