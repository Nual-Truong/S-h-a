from blockchain.ledger import tamper_random_transaction, verify_ledger
from db.database import get_connection
from etl.extract import extract_csv
from etl.load import load_to_db
from etl.transform import transform_data


def run_etl():
    df = extract_csv("data/transactions.csv")
    df_clean = transform_data(df)
    load_to_db(df_clean)


def print_verify_result(label):
    with get_connection() as conn:
        result = verify_ledger(conn, auto_rebuild=False)

    status = "PASSED" if result["valid"] else "FAILED"
    print(f"[{label}] Blockchain integrity check: {status}")
    print(f"[{label}] Blocks: {result['blocks']}")
    print(f"[{label}] Latest hash: {result['latest_hash']}")
    if result["issues"]:
        print(f"[{label}] First issue: {result['issues'][0]}")
    print()


def main():
    print("=== DEMO PASS -> FAIL -> PASS ===")

    print("\n1) Rebuild data and ledger for PASS state...")
    run_etl()
    print_verify_result("STEP 1")

    print("2) Tamper one random transaction for FAIL state...")
    with get_connection() as conn:
        tamper_info = tamper_random_transaction(conn, amount_delta=1234)

    if tamper_info is None:
        print("No transaction found to tamper. Demo stopped.")
        return

    print(
        f"Tampered row {tamper_info['rowid']}: amount {tamper_info['old_amount']} -> {tamper_info['new_amount']}"
    )
    print_verify_result("STEP 2")

    print("3) Rebuild again to recover PASS state...")
    run_etl()
    print_verify_result("STEP 3")


if __name__ == "__main__":
    main()
