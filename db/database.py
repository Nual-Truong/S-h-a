import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "sfm.db")

def get_connection():
    return sqlite3.connect(DB_PATH)