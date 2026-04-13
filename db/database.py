from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "sfm.db")

DEFAULT_PRODUCTS = [
    {
        "product_id": "ML01",
        "product_name": "MayLanhInverter",
        "brand": "Daikin",
        "category": "DienMay",
        "price": 4_900_000,
        "stock": 25,
        "description": "Máy lạnh inverter tiết kiệm điện.",
    },
    {
        "product_id": "TL02",
        "product_name": "TuLanhMini",
        "brand": "Aqua",
        "category": "DienMay",
        "price": 3_800_000,
        "stock": 30,
        "description": "Tủ lạnh mini phù hợp gia đình nhỏ.",
    },
    {
        "product_id": "MG03",
        "product_name": "MayGiatCuaNgang",
        "brand": "LG",
        "category": "DienMay",
        "price": 4_950_000,
        "stock": 20,
        "description": "Máy giặt cửa ngang dung tích lớn.",
    },
    {
        "product_id": "NC04",
        "product_name": "NoiChienKhongDau",
        "brand": "Philips",
        "category": "DienMay",
        "price": 2_300_000,
        "stock": 40,
        "description": "Nồi chiên không dầu đa năng.",
    },
    {
        "product_id": "LK05",
        "product_name": "MayLocKhongKhi",
        "brand": "Sharp",
        "category": "DienMay",
        "price": 3_500_000,
        "stock": 35,
        "description": "Máy lọc không khí cho phòng làm việc.",
    },
]

DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "admin",
        "role": "admin",
        "display_name": "Quản trị viên",
    },
    {
        "username": "viewer",
        "password": "viewer",
        "role": "viewer",
        "display_name": "Người xem",
    },
    {
        "username": "user",
        "password": "user",
        "role": "user",
        "display_name": "Người mua hàng",
    },
]


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES app_users(id)
        );

        CREATE TABLE IF NOT EXISTS purchase_orders (
            order_id TEXT PRIMARY KEY,
            receipt_number TEXT NOT NULL UNIQUE,
            transaction_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES app_users(id)
        );

        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price INTEGER NOT NULL,
            line_total INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES purchase_orders(order_id)
        );
        """
    )

    existing_users = {row[0] for row in conn.execute("SELECT username FROM app_users").fetchall()}
    for account in DEFAULT_USERS:
        if account["username"] not in existing_users:
            conn.execute(
                """
                INSERT INTO app_users (username, password_hash, role, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    account["username"],
                    _hash_password(account["password"]),
                    account["role"],
                    account["display_name"],
                    _utc_now(),
                ),
            )

    existing_products = {row[0] for row in conn.execute("SELECT product_id FROM products").fetchall()}
    for product in DEFAULT_PRODUCTS:
        if product["product_id"] not in existing_products:
            conn.execute(
                """
                INSERT INTO products (
                    product_id, product_name, brand, category, price, stock, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product["product_id"],
                    product["product_name"],
                    product["brand"],
                    product["category"],
                    int(product["price"]),
                    int(product["stock"]),
                    product["description"],
                    _utc_now(),
                    _utc_now(),
                ),
            )

    conn.commit()


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    _ensure_store_schema(conn)
    return conn