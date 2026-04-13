from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import sqlite3

from db.database import get_connection

SESSION_TTL_HOURS = 12


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_number(order_id: str) -> str:
    return f"RCPT-{datetime.now(timezone.utc):%Y%m%d}-{order_id[:8].upper()}"


def _transaction_id() -> str:
    return f"TX-{uuid.uuid4().hex[:12].upper()}"


def authenticate_user(username: str, password: str) -> dict | None:
    username = (username or "").strip()
    if not username or not password:
        return None

    try:
        conn = get_connection()
        try:
            conn.row_factory = None
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, display_name, created_at
                FROM app_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None

    if not row:
        return None

    user_id, found_username, password_hash, role, display_name, created_at = row
    if password_hash != _hash_password(password):
        return None

    return {
        "id": user_id,
        "username": found_username,
        "role": role,
        "display_name": display_name,
        "created_at": created_at,
    }


def create_session(user: dict) -> dict:
    token = f"ses_{uuid.uuid4().hex}"
    created_at = _utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO auth_sessions (token, user_id, username, role, created_at, expires_at, last_seen_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                token,
                user["id"],
                user["username"],
                user["role"],
                created_at,
                expires_at,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "token": token,
        "expires_at": expires_at,
        "user": user,
    }


def get_user_by_session(token: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None

    conn = get_connection()
    try:
        conn.row_factory = None
        row = conn.execute(
            """
            SELECT s.token, s.expires_at, s.is_active, u.id, u.username, u.role, u.display_name, u.created_at
            FROM auth_sessions s
            JOIN app_users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None

        session_token, expires_at, is_active, user_id, username, role, display_name, created_at = row
        if not is_active:
            return None

        expires_at_dt = datetime.fromisoformat(expires_at)
        if expires_at_dt.tzinfo is None:
            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        if expires_at_dt < datetime.now(timezone.utc):
            conn.execute("UPDATE auth_sessions SET is_active = 0 WHERE token = ?", (token,))
            conn.commit()
            return None

        conn.execute("UPDATE auth_sessions SET last_seen_at = ? WHERE token = ?", (_utc_now(), token))
        conn.commit()
    finally:
        conn.close()

    return {
        "token": session_token,
        "id": user_id,
        "username": username,
        "role": role,
        "display_name": display_name,
        "created_at": created_at,
        "expires_at": expires_at,
    }


def list_products() -> list[dict]:
    conn = get_connection()
    try:
        conn.row_factory = None
        rows = conn.execute(
            """
            SELECT product_id, product_name, brand, category, price, stock, description, updated_at
            FROM products
            ORDER BY product_name
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "product_id": row[0],
            "product_name": row[1],
            "brand": row[2],
            "category": row[3],
            "price": row[4],
            "stock": row[5],
            "description": row[6],
            "updated_at": row[7],
        }
        for row in rows
    ]


def get_product(product_id: str) -> dict | None:
    conn = get_connection()
    try:
        conn.row_factory = None
        row = conn.execute(
            """
            SELECT product_id, product_name, brand, category, price, stock, description, updated_at
            FROM products
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    return {
        "product_id": row[0],
        "product_name": row[1],
        "brand": row[2],
        "category": row[3],
        "price": row[4],
        "stock": row[5],
        "description": row[6],
        "updated_at": row[7],
    }


def checkout_order(user: dict, items: list[dict], payment_method: str = "COD") -> dict:
    if not user or user.get("role") not in {"user", "admin"}:
        raise PermissionError("User role does not allow purchase")

    normalized_items = []
    for item in items:
        product_id = str(item.get("product_id") or "").strip()
        quantity = int(item.get("quantity") or 0)
        if not product_id or quantity <= 0:
            raise ValueError("Invalid cart item")
        normalized_items.append({"product_id": product_id, "quantity": quantity})

    if not normalized_items:
        raise ValueError("Cart is empty")

    order_id = uuid.uuid4().hex
    receipt_number = _receipt_number(order_id)
    transaction_id = _transaction_id()
    created_at = _utc_now()
    total_amount = 0
    receipt_items = []

    conn = get_connection()
    try:
        conn.row_factory = None
        conn.execute("BEGIN")
        for item in normalized_items:
            row = conn.execute(
                """
                SELECT product_id, product_name, brand, category, price, stock, description
                FROM products
                WHERE product_id = ?
                """,
                (item["product_id"],),
            ).fetchone()
            if not row:
                raise ValueError(f"Product not found: {item['product_id']}")

            product_id, product_name, brand, category, price, stock, description = row
            if stock < item["quantity"]:
                raise ValueError(f"Insufficient stock for {product_id}")

            line_total = int(price) * item["quantity"]
            total_amount += line_total
            receipt_items.append(
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "brand": brand,
                    "category": category,
                    "quantity": item["quantity"],
                    "unit_price": int(price),
                    "line_total": line_total,
                    "description": description,
                }
            )

        conn.execute(
            """
            INSERT INTO purchase_orders (
                order_id, receipt_number, transaction_id, user_id, username, display_name, role,
                total_amount, payment_method, status, created_at, confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                receipt_number,
                transaction_id,
                user["id"],
                user["username"],
                user.get("display_name") or user["username"],
                user["role"],
                total_amount,
                payment_method,
                "confirmed",
                created_at,
                created_at,
            ),
        )

        for item in receipt_items:
            conn.execute(
                """
                INSERT INTO purchase_order_items (
                    order_id, product_id, product_name, brand, quantity, unit_price, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["product_name"],
                    item["brand"],
                    item["quantity"],
                    item["unit_price"],
                    item["line_total"],
                ),
            )
            conn.execute(
                """
                UPDATE products
                SET stock = stock - ?, updated_at = ?
                WHERE product_id = ?
                """,
                (item["quantity"], created_at, item["product_id"]),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "order_id": order_id,
        "receipt_number": receipt_number,
        "transaction_id": transaction_id,
        "buyer": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": user["role"],
        },
        "items": receipt_items,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "status": "confirmed",
        "created_at": created_at,
        "confirmed_at": created_at,
    }


def list_orders_for_user(username: str) -> list[dict]:
    conn = get_connection()
    try:
        conn.row_factory = None
        rows = conn.execute(
            """
            SELECT order_id, receipt_number, transaction_id, username, display_name, total_amount,
                   payment_method, status, created_at, confirmed_at
            FROM purchase_orders
            WHERE username = ?
            ORDER BY created_at DESC
            """,
            (username,),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "order_id": row[0],
            "receipt_number": row[1],
            "transaction_id": row[2],
            "username": row[3],
            "display_name": row[4],
            "total_amount": row[5],
            "payment_method": row[6],
            "status": row[7],
            "created_at": row[8],
            "confirmed_at": row[9],
        }
        for row in rows
    ]


def get_receipt_by_order_id(order_id: str) -> dict | None:
    conn = get_connection()
    try:
        conn.row_factory = None
        order_row = conn.execute(
            """
            SELECT order_id, receipt_number, transaction_id, username, display_name, role, total_amount,
                   payment_method, status, created_at, confirmed_at
            FROM purchase_orders
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchone()
        if not order_row:
            return None

        item_rows = conn.execute(
            """
            SELECT product_id, product_name, brand, quantity, unit_price, line_total
            FROM purchase_order_items
            WHERE order_id = ?
            ORDER BY id
            """,
            (order_id,),
        ).fetchall()
    finally:
        conn.close()

    return {
        "order_id": order_row[0],
        "receipt_number": order_row[1],
        "transaction_id": order_row[2],
        "buyer": {
            "username": order_row[3],
            "display_name": order_row[4],
            "role": order_row[5],
        },
        "total_amount": order_row[6],
        "payment_method": order_row[7],
        "status": order_row[8],
        "created_at": order_row[9],
        "confirmed_at": order_row[10],
        "items": [
            {
                "product_id": row[0],
                "product_name": row[1],
                "brand": row[2],
                "quantity": row[3],
                "unit_price": row[4],
                "line_total": row[5],
            }
            for row in item_rows
        ],
    }