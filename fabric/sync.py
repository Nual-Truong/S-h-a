from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
from config import FABRIC_HASH_MODE

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FABRIC_ROOT = PROJECT_ROOT / "fabric"
LOG_DIR = PROJECT_ROOT / "logs"
OUTBOX_DIR = FABRIC_ROOT / "outbox"
PAYLOAD_PATH = OUTBOX_DIR / "financial-assets.json"
MANIFEST_PATH = OUTBOX_DIR / "sync-manifest.json"
STATUS_PATH = OUTBOX_DIR / "sync-status.json"
CHECKPOINT_PATH = OUTBOX_DIR / "sync-checkpoint.json"
RUNTIME_LOG_PATH = LOG_DIR / "runtime-log.jsonl"


def _find_node_binary() -> str | None:
    node_binary = shutil.which("node")
    if node_binary:
        return node_binary

    # Windows fallback when PATH is not loaded in current shell/session.
    fallback_paths = [
        Path("C:/Program Files/nodejs/node.exe"),
        Path("C:/Program Files (x86)/nodejs/node.exe"),
    ]
    for candidate in fallback_paths:
        if candidate.exists():
            return str(candidate)

    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_runtime_log(component: str, status: str, message: str, extra: dict | None = None) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _utc_now(),
        "component": component,
        "status": status,
        "message": message,
        "extra": extra or {},
    }
    with RUNTIME_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def get_recent_runtime_logs(limit: int = 20) -> list[dict]:
    if not RUNTIME_LOG_PATH.exists():
        return []

    lines = RUNTIME_LOG_PATH.read_text(encoding="utf-8").splitlines()
    entries: list[dict] = []
    for raw_line in lines[-limit:]:
        try:
            entries.append(json.loads(raw_line))
        except Exception:
            entries.append({"timestamp": None, "component": "unknown", "status": "unknown", "message": raw_line, "extra": {}})
    return entries


def _safe_int(value):
    if pd.isna(value):
        return None
    try:
        return int(value)
    except Exception:
        return value


def _build_transaction_key(row: pd.Series, index: int) -> str:
    product_id = str(row.get("product_id") or row.get("asset_id") or "UNKNOWN")
    date_value = str(row.get("date") or "unknown-date").replace(" ", "T").replace(":", "-")
    # Unique deterministic key per row so each transaction is a separate on-chain record.
    return f"TX-{index + 1:06d}-{product_id}-{date_value}"


def _row_to_asset(row: pd.Series, index: int) -> dict:
    product_id = row.get("product_id") or row.get("asset_id") or f"ASSET-{index + 1:06d}"
    asset_id = _build_transaction_key(row, index)
    return {
        "asset_id": str(asset_id),
        "payload": {
            "product_id": str(product_id),
            "date": str(row.get("date")),
            "category": str(row.get("category")),
            "product_name": str(row.get("product_name", "")),
            "product_code": str(row.get("product_code", "")),
            "brand": str(row.get("brand", "")),
            "amount": _safe_int(row.get("amount")),
            "cost": _safe_int(row.get("cost")),
            "profit": _safe_int(row.get("profit")),
        },
    }


def _build_transaction_hash(asset: dict) -> str:
    canonical = json.dumps(
        {"asset_id": asset.get("asset_id"), "payload": asset.get("payload", {})},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def export_fabric_payload(df: pd.DataFrame, source_name: str = "transactions") -> dict:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

    normalized = df.copy().reset_index(drop=True)
    assets = [_row_to_asset(row, index) for index, (_, row) in enumerate(normalized.iterrows())]

    if FABRIC_HASH_MODE in {"per-transaction", "both"}:
        for asset in assets:
            asset["transaction_hash"] = _build_transaction_hash(asset)

    payload = {
        "source": source_name,
        "exported_at": _utc_now(),
        "hash_mode": FABRIC_HASH_MODE,
        "count": len(assets),
        "assets": assets,
    }

    PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "source": source_name,
        "payload_path": str(PAYLOAD_PATH),
        "count": len(assets),
        "exported_at": payload["exported_at"],
        "status": "pending",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    append_runtime_log("fabric_outbox", "exported", f"Exported {len(assets)} assets to Fabric outbox.", {"source": source_name, "count": len(assets)})

    return payload


def record_fabric_status(status: str, message: str, count: int | None = None) -> dict:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    status_payload = {
        "status": status,
        "message": message,
        "count": count,
        "updated_at": _utc_now(),
    }
    STATUS_PATH.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_runtime_log("fabric_status", status, message, {"count": count})

    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["status"] = status
        manifest["message"] = message
        manifest["updated_at"] = status_payload["updated_at"]
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return status_payload


def get_fabric_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))

    return {
        "status": "idle",
        "next_offset": 0,
        "completed": 0,
        "target": None,
        "batch_size": None,
        "commit_timeout": None,
        "last_message": None,
        "updated_at": None,
    }


def save_fabric_checkpoint(payload: dict) -> dict:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "status": payload.get("status", "running"),
        "next_offset": int(payload.get("next_offset", 0) or 0),
        "completed": int(payload.get("completed", 0) or 0),
        "target": payload.get("target"),
        "batch_size": payload.get("batch_size"),
        "commit_timeout": payload.get("commit_timeout"),
        "last_message": payload.get("last_message"),
        "updated_at": _utc_now(),
    }
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    return checkpoint


def clear_fabric_checkpoint() -> bool:
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        append_runtime_log("fabric_checkpoint", "cleared", "Auto-resume checkpoint cleared.")
        return True
    return False


def get_fabric_status() -> dict:
    if STATUS_PATH.exists():
        status_payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    else:
        status_payload = {
            "status": "not_synced",
            "message": "Chưa có dữ liệu Fabric outbox.",
            "count": None,
            "updated_at": None,
        }

    manifest = None
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    payload_count = None
    if PAYLOAD_PATH.exists():
        try:
            payload_count = len(json.loads(PAYLOAD_PATH.read_text(encoding="utf-8")).get("assets", []))
        except Exception:
            payload_count = None

    return {
        "status": status_payload.get("status", "not_synced"),
        "message": status_payload.get("message", ""),
        "count": status_payload.get("count", payload_count),
        "updated_at": status_payload.get("updated_at"),
        "payload_path": str(PAYLOAD_PATH) if PAYLOAD_PATH.exists() else None,
        "manifest": manifest,
    }


def summarize_fabric_outbox() -> dict:
    status = get_fabric_status()
    if not PAYLOAD_PATH.exists():
        return {
            "valid": False,
            "issues": ["Chưa có payload outbox cho Fabric."],
            "asset_count": 0,
            "payload_hash": None,
            "status": status,
        }

    try:
        raw_content = PAYLOAD_PATH.read_text(encoding="utf-8")
        payload = json.loads(raw_content)
        assets = payload.get("assets", [])
        hash_mode = payload.get("hash_mode") or FABRIC_HASH_MODE

        payload_hash = None
        if hash_mode in {"total", "both"}:
            payload_hash = sha256(raw_content.encode("utf-8")).hexdigest()

        tx_hash_count = 0
        tx_hash_samples = []
        if hash_mode in {"per-transaction", "both"}:
            for asset in assets:
                tx_hash = asset.get("transaction_hash") or _build_transaction_hash(asset)
                tx_hash_count += 1
                if len(tx_hash_samples) < 10:
                    tx_hash_samples.append(
                        {
                            "asset_id": asset.get("asset_id"),
                            "transaction_hash": tx_hash,
                        }
                    )

        return {
            "valid": True,
            "issues": [],
            "asset_count": len(assets),
            "hash_mode": hash_mode,
            "payload_hash": payload_hash,
            "transaction_hash_count": tx_hash_count,
            "transaction_hash_samples": tx_hash_samples,
            "status": status,
        }
    except Exception as exc:
        return {
            "valid": False,
            "issues": [f"Payload outbox không hợp lệ: {exc}"],
            "asset_count": 0,
            "payload_hash": None,
            "status": status,
        }


def run_fabric_client() -> dict:
    node_binary = _find_node_binary()
    client_script = FABRIC_ROOT / "client" / "invoke-client.js"
    asset_count = get_fabric_status().get("count")

    if not node_binary:
        append_runtime_log("fabric_client", "dry_run", "Node.js not found; skipped Fabric client run.", {"asset_count": asset_count})
        return record_fabric_status(
            "dry_run",
            "Node.js chưa có trong PATH, chỉ xuất outbox Fabric.",
            count=asset_count,
        )

    try:
        completed = subprocess.run(
            [node_binary, str(client_script)],
            cwd=str(client_script.parent),
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "FABRIC_INPUT_PATH": str(PAYLOAD_PATH)},
        )
        return record_fabric_status(
            "synced",
            completed.stdout.strip() or "Fabric client completed successfully.",
            count=asset_count,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        append_runtime_log("fabric_client", "error", message, {"asset_count": asset_count})
        return record_fabric_status("error", message, count=asset_count)
