import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from blockchain.merkle import compute_merkle_root
from blockchain.security import (
    generate_security_id,
    get_secret_fingerprint,
    sign_block_payload,
    verify_block_signature,
)

LEDGER_TABLE = "transaction_ledger"
AUDIT_TABLE = "ledger_audit_log"
META_TABLE = "ledger_meta"
ANCHOR_TABLE = "ledger_anchor_log"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_record(row: pd.Series) -> str:
    payload = {
        "date": str(row["date"]),
        "category": str(row["category"]),
        "amount": int(row["amount"]),
        "cost": int(row["cost"]),
        "profit": int(row["profit"]),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _build_expected_chain(df: pd.DataFrame):
    ordered_df = (
        df[["date", "category", "amount", "cost", "profit"]]
        .copy()
        .sort_values(["date", "category", "amount", "cost", "profit"])
        .reset_index(drop=True)
    )

    data_hashes = []
    for _, row in ordered_df.iterrows():
        data_hashes.append(_sha256(_normalize_record(row)))

    merkle_root = compute_merkle_root(data_hashes)

    expected = []
    prev_hash = "0" * 64

    for block_index, data_hash in enumerate(data_hashes):
        security_id = generate_security_id(block_index, data_hash, prev_hash)
        core_payload = f"{block_index}|{data_hash}|{prev_hash}|{security_id}|{merkle_root}"
        signature = sign_block_payload(core_payload)
        block_hash = _sha256(f"{core_payload}|{signature}")
        expected.append(
            (block_index, data_hash, prev_hash, security_id, merkle_root, signature, block_hash)
        )
        prev_hash = block_hash

    return expected, merkle_root


def _ensure_ledger_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
            block_index INTEGER PRIMARY KEY,
            data_hash TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            security_id TEXT,
            merkle_root TEXT,
            signature TEXT,
            block_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _ensure_column(conn, table_name: str, column_name: str, column_type: str):
    existing = pd.read_sql(f"PRAGMA table_info({table_name})", conn)["name"].tolist()
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        conn.commit()


def _ensure_audit_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            status TEXT NOT NULL,
            blocks INTEGER NOT NULL,
            latest_hash TEXT,
            latest_security_id TEXT,
            merkle_root TEXT,
            issue_count INTEGER NOT NULL,
            issue_preview TEXT
        )
        """
    )


def _ensure_meta_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {META_TABLE} (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _ensure_anchor_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ANCHOR_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anchored_at TEXT NOT NULL,
            latest_hash TEXT NOT NULL,
            merkle_root TEXT NOT NULL,
            anchor_hash TEXT NOT NULL,
            note TEXT
        )
        """
    )


def _set_meta_value(conn, key: str, value: str):
    updated_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        f"""
        INSERT INTO {META_TABLE} (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            updated_at=excluded.updated_at
        """,
        (key, str(value), updated_at),
    )


def _get_meta_value(conn, key: str):
    row = conn.execute(f"SELECT value FROM {META_TABLE} WHERE key = ?", (key,)).fetchone()
    return None if not row else row[0]


def create_anchor_snapshot(conn, latest_hash: str, merkle_root: str, note: str = "manual"):
    payload = f"{latest_hash}|{merkle_root}|{note}"
    anchor_hash = _sha256(payload)
    anchored_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        f"""
        INSERT INTO {ANCHOR_TABLE} (anchored_at, latest_hash, merkle_root, anchor_hash, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (anchored_at, latest_hash, merkle_root, anchor_hash, note),
    )

    _set_meta_value(conn, "latest_anchor_hash", anchor_hash)
    conn.commit()
    return anchor_hash


def get_recent_anchor_logs(conn, limit=10):
    _ensure_anchor_table(conn)
    return pd.read_sql(
        f"""
        SELECT anchored_at, latest_hash, merkle_root, anchor_hash, note
        FROM {ANCHOR_TABLE}
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )


def _save_audit(conn, result):
    checked_at = datetime.now(timezone.utc).isoformat()
    status = "PASSED" if result["valid"] else "FAILED"
    issue_count = len(result["issues"])
    issue_preview = "; ".join(result["issues"][:3]) if result["issues"] else ""

    conn.execute(
        f"""
        INSERT INTO {AUDIT_TABLE}
        (checked_at, status, blocks, latest_hash, latest_security_id, merkle_root, issue_count, issue_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            checked_at,
            status,
            int(result["blocks"]),
            result["latest_hash"],
            result.get("latest_security_id"),
            result.get("merkle_root"),
            issue_count,
            issue_preview,
        ),
    )
    conn.commit()


def get_recent_audit_logs(conn, limit=10):
    _ensure_audit_table(conn)
    _ensure_column(conn, AUDIT_TABLE, "latest_security_id", "TEXT")
    _ensure_column(conn, AUDIT_TABLE, "merkle_root", "TEXT")
    return pd.read_sql(
        f"""
        SELECT checked_at, status, blocks, latest_hash, latest_security_id, merkle_root, issue_count, issue_preview
        FROM {AUDIT_TABLE}
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )


def rebuild_ledger(conn, df: pd.DataFrame):
    _ensure_ledger_table(conn)
    _ensure_audit_table(conn)
    _ensure_meta_table(conn)
    _ensure_anchor_table(conn)

    _ensure_column(conn, LEDGER_TABLE, "security_id", "TEXT")
    _ensure_column(conn, LEDGER_TABLE, "merkle_root", "TEXT")
    _ensure_column(conn, LEDGER_TABLE, "signature", "TEXT")

    expected_chain, merkle_root = _build_expected_chain(df)
    conn.execute(f"DELETE FROM {LEDGER_TABLE}")

    created_at = datetime.now(timezone.utc).isoformat()
    records = [
        (
            block_index,
            data_hash,
            prev_hash,
            security_id,
            merkle_root_value,
            signature,
            block_hash,
            created_at,
        )
        for (
            block_index,
            data_hash,
            prev_hash,
            security_id,
            merkle_root_value,
            signature,
            block_hash,
        ) in expected_chain
    ]

    if records:
        conn.executemany(
            f"""
            INSERT INTO {LEDGER_TABLE}
            (block_index, data_hash, prev_hash, security_id, merkle_root, signature, block_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

    latest_security_id = records[-1][3] if records else None
    latest_hash = records[-1][6] if records else None

    _set_meta_value(conn, "merkle_root", merkle_root)
    _set_meta_value(conn, "key_fingerprint", get_secret_fingerprint())
    anchor_hash = None
    if latest_hash and merkle_root:
        anchor_hash = create_anchor_snapshot(conn, latest_hash, merkle_root, note="rebuild")

    conn.commit()
    return {
        "blocks": len(records),
        "latest_hash": latest_hash,
        "latest_security_id": latest_security_id,
        "merkle_root": merkle_root,
        "anchor_hash": anchor_hash,
    }


def verify_ledger(conn, auto_rebuild=False):
    _ensure_ledger_table(conn)
    _ensure_audit_table(conn)
    _ensure_meta_table(conn)
    _ensure_anchor_table(conn)

    _ensure_column(conn, LEDGER_TABLE, "security_id", "TEXT")
    _ensure_column(conn, LEDGER_TABLE, "merkle_root", "TEXT")
    _ensure_column(conn, LEDGER_TABLE, "signature", "TEXT")

    _ensure_column(conn, AUDIT_TABLE, "latest_security_id", "TEXT")
    _ensure_column(conn, AUDIT_TABLE, "merkle_root", "TEXT")

    def _finalize(result):
        _save_audit(conn, result)
        return result

    issues = []
    first_mismatch_block = None

    def _add_issue(message: str, block_idx=None):
        nonlocal first_mismatch_block
        issues.append(message)
        if block_idx is not None and first_mismatch_block is None:
            first_mismatch_block = int(block_idx)

    try:
        tx_df = pd.read_sql("SELECT date, category, amount, cost, profit FROM transactions", conn)
    except Exception as exc:
        return _finalize(
            {
                "valid": False,
                "issues": [f"Không thể truy cập bảng transactions: {exc}"],
                "blocks": 0,
                "latest_hash": None,
                "latest_security_id": None,
                "merkle_root": None,
                "anchor_hash": None,
                "first_mismatch_block": None,
            }
        )

    ledger_df = pd.read_sql(
        f"""
        SELECT block_index, data_hash, prev_hash, security_id, merkle_root, signature, block_hash
        FROM {LEDGER_TABLE}
        ORDER BY block_index
        """,
        conn,
    )

    expected_chain, expected_merkle_root = _build_expected_chain(tx_df)
    stored_merkle_root = _get_meta_value(conn, "merkle_root")
    stored_key_fingerprint = _get_meta_value(conn, "key_fingerprint")
    current_key_fingerprint = get_secret_fingerprint()

    has_missing_security_id = False
    if not ledger_df.empty:
        security_series = ledger_df["security_id"]
        has_missing_security_id = bool(
            security_series.isna().any()
            or security_series.astype(str).str.strip().eq("").any()
            or security_series.astype(str).str.lower().eq("nan").any()
            or security_series.astype(str).str.lower().eq("none").any()
        )

    if auto_rebuild and expected_chain and (ledger_df.empty or has_missing_security_id):
        rebuilt = rebuild_ledger(conn, tx_df)
        rebuild_reason = "Sổ cái trống và đã được tạo lại tự động."
        if has_missing_security_id:
            rebuild_reason = "Sổ cái thiếu Security ID và đã được tạo lại tự động."
        return _finalize(
            {
                "valid": True,
                "issues": [rebuild_reason],
                "blocks": rebuilt["blocks"],
                "latest_hash": rebuilt["latest_hash"],
                "latest_security_id": rebuilt["latest_security_id"],
                "merkle_root": rebuilt["merkle_root"],
                "anchor_hash": rebuilt["anchor_hash"],
                "first_mismatch_block": None,
            }
        )

    key_mismatch = (
        stored_key_fingerprint is not None
        and stored_key_fingerprint != current_key_fingerprint
    )
    if key_mismatch:
        if auto_rebuild and expected_chain:
            rebuilt = rebuild_ledger(conn, tx_df)
            return _finalize(
                {
                    "valid": True,
                    "issues": [
                        "Phát hiện thay đổi khóa bảo mật, đã tự động rebuild sổ cái theo khóa hiện tại."
                    ],
                    "blocks": rebuilt["blocks"],
                    "latest_hash": rebuilt["latest_hash"],
                    "latest_security_id": rebuilt["latest_security_id"],
                    "merkle_root": rebuilt["merkle_root"],
                    "anchor_hash": rebuilt["anchor_hash"],
                    "first_mismatch_block": None,
                }
            )

        _add_issue(
            "Khóa bảo mật hiện tại khác với khóa dùng để tạo sổ cái. Hãy chạy lại ETL hoặc bật auto_rebuild."
        )

    if len(expected_chain) != len(ledger_df):
        _add_issue("Số lượng khối không khớp giữa bảng giao dịch và sổ cái blockchain.")

    if stored_merkle_root != expected_merkle_root:
        _add_issue("Merkle root không khớp giữa dữ liệu hiện tại và metadata blockchain.")

    comparison_len = min(len(expected_chain), len(ledger_df))

    for i in range(comparison_len):
        (
            exp_idx,
            exp_data_hash,
            exp_prev_hash,
            exp_security_id,
            exp_merkle_root,
            exp_signature,
            exp_block_hash,
        ) = expected_chain[i]

        row = ledger_df.iloc[i]

        if int(row["block_index"]) != exp_idx:
            _add_issue(f"Chỉ số khối không hợp lệ tại vị trí {i}.", exp_idx)

        if row["data_hash"] != exp_data_hash:
            _add_issue(f"Data hash không khớp tại khối {exp_idx}.", exp_idx)

        if row["prev_hash"] != exp_prev_hash:
            _add_issue(f"Previous hash không khớp tại khối {exp_idx}.", exp_idx)

        if row["security_id"] != exp_security_id:
            _add_issue(f"Security ID không khớp tại khối {exp_idx}.", exp_idx)

        if row["merkle_root"] != exp_merkle_root:
            _add_issue(f"Merkle root không khớp tại khối {exp_idx}.", exp_idx)

        if row["signature"] != exp_signature:
            _add_issue(f"Chữ ký số không khớp tại khối {exp_idx}.", exp_idx)

        core_payload = (
            f"{exp_idx}|{exp_data_hash}|{exp_prev_hash}|{exp_security_id}|{exp_merkle_root}"
        )
        if not verify_block_signature(core_payload, str(row["signature"])):
            _add_issue(f"Chữ ký số không hợp lệ tại khối {exp_idx}.", exp_idx)

        if row["block_hash"] != exp_block_hash:
            _add_issue(f"Block hash không khớp tại khối {exp_idx}.", exp_idx)

    latest_hash = None
    latest_security_id = None
    anchor_hash = _get_meta_value(conn, "latest_anchor_hash")

    if not ledger_df.empty:
        latest_hash = str(ledger_df.iloc[-1]["block_hash"])
        raw_security_id = ledger_df.iloc[-1]["security_id"]
        if not pd.isna(raw_security_id):
            normalized_security_id = str(raw_security_id).strip()
            if normalized_security_id and normalized_security_id.lower() not in {"none", "nan"}:
                latest_security_id = normalized_security_id

    if latest_hash and expected_merkle_root and anchor_hash:
        anchor_df = get_recent_anchor_logs(conn, limit=1)
        if not anchor_df.empty:
            row = anchor_df.iloc[0]
            expected_anchor = _sha256(f"{row['latest_hash']}|{row['merkle_root']}|{row['note']}")
            if expected_anchor != row["anchor_hash"]:
                _add_issue("Anchor hash snapshot đã bị thay đổi hoặc không hợp lệ.")

    return _finalize(
        {
            "valid": len(issues) == 0,
            "issues": issues,
            "blocks": len(ledger_df),
            "latest_hash": latest_hash,
            "latest_security_id": latest_security_id,
            "merkle_root": expected_merkle_root,
            "anchor_hash": anchor_hash,
            "first_mismatch_block": first_mismatch_block,
        }
    )


def tamper_random_transaction(conn, amount_delta=999):
    cursor = conn.execute("SELECT rowid, amount, cost FROM transactions ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()

    if not row:
        return None

    rowid, amount, cost = int(row[0]), int(row[1]), int(row[2])
    new_amount = amount + int(amount_delta)
    new_profit = new_amount - cost

    conn.execute(
        "UPDATE transactions SET amount = ?, profit = ? WHERE rowid = ?",
        (new_amount, new_profit, rowid),
    )
    conn.commit()

    return {
        "rowid": rowid,
        "old_amount": amount,
        "new_amount": new_amount,
    }
