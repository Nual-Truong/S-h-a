from db.database import get_connection
from blockchain.ledger import rebuild_ledger

def load_to_db(df):
    with get_connection() as conn:
        df.to_sql("transactions", conn, if_exists="replace", index=False)
        ledger_info = rebuild_ledger(conn, df)

    print("Data loaded successfully")
    print(
        f"Blockchain ledger rebuilt: {ledger_info['blocks']} blocks, latest hash: {ledger_info['latest_hash']}, latest security ID: {ledger_info['latest_security_id']}, merkle root: {ledger_info['merkle_root']}, anchor hash: {ledger_info['anchor_hash']}"
    )