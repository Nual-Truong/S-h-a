import pandas as pd

MAX_MONETARY_VALUE = 5_000_000

def transform_data(df: pd.DataFrame):
    required_columns = ["date", "category", "amount", "cost"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df.copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")

    df = df.dropna(subset=["date", "category", "amount", "cost"])
    df = df[(df["amount"] >= 0) & (df["cost"] >= 0)]

    # Clamp extreme values to keep analysis in a stable range.
    df["amount"] = df["amount"].clip(upper=MAX_MONETARY_VALUE)
    df["cost"] = df["cost"].clip(upper=MAX_MONETARY_VALUE)

    df["amount"] = df["amount"].astype(int)
    df["cost"] = df["cost"].astype(int)
    df["category"] = df["category"].astype(str)
    df["profit"] = df["amount"] - df["cost"]

    return df