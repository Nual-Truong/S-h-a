from db.database import get_connection
from blockchain.ledger import verify_ledger


def main():
    with get_connection() as conn:
        result = verify_ledger(conn)

    if result["valid"]:
        print("Blockchain integrity check: PASSED")
    else:
        print("Blockchain integrity check: FAILED")
        for issue in result["issues"]:
            print(f"- {issue}")

    print(f"Blocks: {result['blocks']}")
    print(f"Latest hash: {result['latest_hash']}")
    print(f"Latest security ID: {result.get('latest_security_id')}")
    print(f"Merkle root: {result.get('merkle_root')}")
    print(f"Latest anchor hash: {result.get('anchor_hash')}")
    print(f"First mismatch block: {result.get('first_mismatch_block')}")


if __name__ == "__main__":
    main()
