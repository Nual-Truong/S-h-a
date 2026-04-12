from __future__ import annotations

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response

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

app = FastAPI(title="Financial Data API", version="1.0.0")


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


def _build_report_sections(transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if transactions.empty:
        return {
            "overview": transactions,
            "trend": pd.DataFrame(),
            "anomalies": pd.DataFrame(),
            "forecast": pd.DataFrame(),
            "seasonality": pd.DataFrame(),
        }

    trend = (
        transactions.dropna(subset=["date", "category", "amount"])
        .assign(date=lambda x: x["date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["date", "category"], as_index=False)["amount"]
        .sum()
    )
    anomalies = pd.DataFrame(columns=["date", "category", "amount", "cost", "profit"])
    forecast = transactions.groupby("category", as_index=False)["amount"].sum().rename(columns={"amount": "Forecast"})
    seasonality = transactions.assign(month=transactions["date"].dt.month).groupby("month", as_index=False)["amount"].sum()

    return {
        "overview": transactions.copy(),
        "trend": trend,
        "anomalies": anomalies,
        "forecast": forecast,
        "seasonality": seasonality,
    }


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
