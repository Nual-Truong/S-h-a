from __future__ import annotations

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import cast

from config import DASHBOARD_ADMIN_PASSWORD
from db.database import get_connection
from fabric.sync import (
    append_runtime_log,
    clear_fabric_checkpoint,
    get_fabric_checkpoint,
    get_fabric_status,
    get_recent_runtime_logs,
    run_fabric_client,
    summarize_fabric_outbox,
)
from services.reporting import build_excel_report_bytes, build_pdf_report_bytes
from services.store import (
    authenticate_user,
    checkout_order,
    create_session,
    get_product,
    get_receipt_by_order_id,
    get_user_by_session,
    list_orders_for_user,
    list_products,
)

app = FastAPI(title="Financial Data API", version="1.0.0")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CheckoutItemRequest(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)


class CheckoutRequest(BaseModel):
    items: list[CheckoutItemRequest] = Field(min_length=1)
    payment_method: str = Field(default="COD")


def _is_admin(password: str | None) -> bool:
    if not DASHBOARD_ADMIN_PASSWORD:
        return True
    return bool(password) and password == DASHBOARD_ADMIN_PASSWORD


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict:
    return {
        "fabric_status": get_fabric_status(),
        "fabric_integrity": summarize_fabric_outbox(),
        "fabric_checkpoint": get_fabric_checkpoint(),
        "recent_logs": get_recent_runtime_logs(limit=10),
    }


@app.get("/logs")
def logs(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"items": get_recent_runtime_logs(limit=limit)}

#FAST API đăng nhập
@app.post("/auth/login")
def login(payload: LoginRequest) -> JSONResponse:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session = create_session(user)
    return JSONResponse(
        {
            "token_type": "bearer",
            "access_token": session["token"],
            "expires_at": session["expires_at"],
            "user": session["user"],
        }
    )

#report bên đăng nhập user
@app.get("/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    user = get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user": user}

#API về produdct, checkout, order, receipt
@app.get("/products")
def products() -> dict:
    return {"items": list_products()}


@app.get("/products/{product_id}")
def product_detail(product_id: str) -> dict:
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/checkout")
def checkout(payload: CheckoutRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    token = _extract_bearer_token(authorization)
    user = get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    receipt = checkout_order(
        user,
        [{"product_id": item.product_id, "quantity": item.quantity} for item in payload.items],
        payment_method=payload.payment_method,
    )
    append_runtime_log("api", "checkout", f"User {user['username']} created order {receipt['order_id']}", {"order_id": receipt["order_id"]})
    return JSONResponse(receipt)


@app.get("/orders/me")
def orders_me(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    user = get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"items": list_orders_for_user(user["username"])}


@app.get("/orders/{order_id}/receipt")
def receipt(order_id: str, authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    user = get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    receipt_data = get_receipt_by_order_id(order_id)
    if not receipt_data:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if user["role"] != "admin" and receipt_data["buyer"]["username"] != user["username"]:
        raise HTTPException(status_code=403, detail="Not allowed to access this receipt")

    return receipt_data


def _build_report_sections(transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if transactions.empty:
        return {
            "overview": transactions,
            "trend": pd.DataFrame(),
            "anomalies": pd.DataFrame(),
            "forecast": pd.DataFrame(),
            "seasonality": pd.DataFrame(),
        }

    trend = cast(
        pd.DataFrame,
        (
        transactions.dropna(subset=["date", "category", "amount"])
        .assign(date=lambda x: x["date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["date", "category"], as_index=False)["amount"]
        .sum()
        ),
    )
    anomalies: pd.DataFrame = pd.DataFrame(columns=["date", "category", "amount", "cost", "profit"])
    forecast: pd.DataFrame = transactions.groupby("category", as_index=False).agg(Forecast=("amount", "sum"))
    seasonality: pd.DataFrame = (
        transactions.assign(month=transactions["date"].dt.month)
        .groupby("month", as_index=False)
        .agg(amount=("amount", "sum"))
    )

    sections: dict[str, pd.DataFrame] = {
        "overview": transactions.copy(),
        "trend": trend,
        "anomalies": anomalies,
        "forecast": forecast,
        "seasonality": seasonality,
    }
    return sections


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2:
        return ""
    scheme, token = parts
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


@app.get("/report.xlsx")
def report_xlsx() -> Response:
    conn = get_connection()
    try:
        transactions = pd.read_sql("SELECT * FROM transactions", conn)
    finally:
        conn.close()

    if not transactions.empty and "date" in transactions.columns:
        transactions["date"] = pd.to_datetime(transactions["date"], errors="coerce")

    sections = _build_report_sections(transactions)

    report_bytes = build_excel_report_bytes(
        sections
    )
    append_runtime_log("api", "report", "Generated Excel report from API.")
    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="financial_api_report.xlsx"'},
    )


@app.get("/report.pdf")
def report_pdf() -> Response:
    conn = get_connection()
    try:
        transactions = pd.read_sql("SELECT * FROM transactions", conn)
    finally:
        conn.close()

    if not transactions.empty and "date" in transactions.columns:
        transactions["date"] = pd.to_datetime(transactions["date"], errors="coerce")

    sections = _build_report_sections(transactions)
    report_bytes = build_pdf_report_bytes(
        "Financial Data Report",
        sections,
        subtitle="Báo cáo PDF được tạo từ API, gồm tổng quan, xu hướng, dự báo và mùa vụ.",
    )
    append_runtime_log("api", "report", "Generated PDF report from API.")
    return Response(
        content=report_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="financial_api_report.pdf"'},
    )


@app.post("/admin/fabric/sync")
def trigger_fabric_sync(x_admin_password: str | None = Header(default=None)) -> JSONResponse:
    if not _is_admin(x_admin_password):
        raise HTTPException(status_code=403, detail="Admin password required")

    result = run_fabric_client()
    append_runtime_log("api", result.get("status", "unknown"), result.get("message", "Fabric sync triggered from API."))
    return JSONResponse(result)


@app.post("/admin/checkpoint/clear")
def clear_checkpoint(x_admin_password: str | None = Header(default=None)) -> dict:
    if not _is_admin(x_admin_password):
        raise HTTPException(status_code=403, detail="Admin password required")

    cleared = clear_fabric_checkpoint()
    append_runtime_log("api", "checkpoint_cleared", "API cleared Fabric checkpoint.", {"cleared": cleared})
    return {"cleared": cleared}
