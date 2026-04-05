import pandas as pd
from db.database import get_connection

def analyze_trend():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM transactions", conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])

    trend = df.groupby([df["date"].dt.to_period("M"), "category"]) \
              .agg({"amount": "sum"}) \
              .reset_index()

    trend["date"] = trend["date"].astype(str)

    return trend