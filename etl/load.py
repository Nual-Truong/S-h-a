from config import ENABLE_LEGACY_BLOCKCHAIN, FABRIC_AUTO_SYNC
from db.database import get_connection
from fabric.sync import append_runtime_log, export_fabric_payload, record_fabric_status, run_fabric_client

if ENABLE_LEGACY_BLOCKCHAIN:
    from blockchain.ledger import rebuild_ledger

def load_to_db(df):
    ledger_info = None
    with get_connection() as conn:
        df.to_sql("transactions", conn, if_exists="replace", index=False)
        if ENABLE_LEGACY_BLOCKCHAIN:
            ledger_info = rebuild_ledger(conn, df)

    fabric_payload = export_fabric_payload(df)
    if FABRIC_AUTO_SYNC:
        fabric_status = run_fabric_client()
    else:
        fabric_status = record_fabric_status(
            "pending",
            "Đã export outbox. Bật FABRIC_AUTO_SYNC=1 để tự đồng bộ Fabric.",
            count=len(fabric_payload.get("assets", [])),
        )

    if fabric_status.get("status") in {"error", "dry_run"}:
        record_fabric_status(
            fabric_status["status"],
            fabric_status.get("message", "Fabric sync chưa hoàn tất."),
            count=len(fabric_payload.get("assets", [])),
        )

    print("Data loaded successfully")
    if ledger_info is not None:
        print(
            f"Blockchain ledger rebuilt: {ledger_info['blocks']} blocks, latest hash: {ledger_info['latest_hash']}, latest security ID: {ledger_info['latest_security_id']}, merkle root: {ledger_info['merkle_root']}, anchor hash: {ledger_info['anchor_hash']}"
        )
    else:
        print("Legacy blockchain rebuild skipped (Fabric-first mode).")

    print(
        f"Fabric outbox exported: {len(fabric_payload['assets'])} assets, status: {fabric_status.get('status')}, message: {fabric_status.get('message')}"
    )
    append_runtime_log(
        "etl",
        fabric_status.get("status", "completed"),
        "ETL completed successfully",
        {
            "rows": int(len(df)),
            "fabric_status": fabric_status.get("status"),
            "fabric_count": len(fabric_payload.get("assets", [])),
        },
    )