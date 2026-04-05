import pandas as pd
from db.database import get_connection

def analyze_seasonality():
    with get_connection() as conn:
        df = pd.read_sql("SELECT date, amount FROM transactions", conn)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    df["month"] = df["date"].dt.month

    season = (
        df.groupby("month")["amount"]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    return season