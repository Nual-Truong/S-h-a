import pandas as pd
from sklearn.ensemble import IsolationForest
from db.database import get_connection


def _build_anomaly_reason(row, bounds):
    reasons = []

    if row["amount"] > bounds["amount_high"]:
        reasons.append("Doanh thu cao bất thường")
    elif row["amount"] < bounds["amount_low"]:
        reasons.append("Doanh thu thấp bất thường")

    if row["cost"] > bounds["cost_high"]:
        reasons.append("Chi phí cao bất thường")
    elif row["cost"] < bounds["cost_low"]:
        reasons.append("Chi phí thấp bất thường")

    if row["profit"] > bounds["profit_high"]:
        reasons.append("Lợi nhuận cao bất thường")
    elif row["profit"] < bounds["profit_low"]:
        reasons.append("Lợi nhuận thấp bất thường")

    if row["profit_margin"] > bounds["margin_high"]:
        reasons.append("Biên lợi nhuận cao bất thường")
    elif row["profit_margin"] < bounds["margin_low"]:
        reasons.append("Biên lợi nhuận thấp bất thường")

    if not reasons:
        return "Mẫu giao dịch lệch cụm chung (IsolationForest)"

    return "; ".join(reasons)


def detect_anomalies():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM transactions", conn)
    conn.close()

    if df.empty:
        return df

    df = df.copy()
    safe_amount = df["amount"].replace(0, pd.NA)
    df["profit_margin"] = (df["profit"] / safe_amount).fillna(0.0)

    model = IsolationForest(contamination=0.05, random_state=42)
    df["anomaly"] = model.fit_predict(df[["amount","cost","profit"]])
    df["anomaly_score"] = model.decision_function(df[["amount", "cost", "profit"]])

    bounds = {
        "amount_low": df["amount"].quantile(0.05),
        "amount_high": df["amount"].quantile(0.95),
        "cost_low": df["cost"].quantile(0.05),
        "cost_high": df["cost"].quantile(0.95),
        "profit_low": df["profit"].quantile(0.05),
        "profit_high": df["profit"].quantile(0.95),
        "margin_low": df["profit_margin"].quantile(0.05),
        "margin_high": df["profit_margin"].quantile(0.95),
    }

    anomalies = df[df["anomaly"] == -1].copy()
    anomalies["anomaly_reason"] = anomalies.apply(
        lambda row: _build_anomaly_reason(row, bounds),
        axis=1,
    )

    if len(anomalies) > 30:
        anomalies = anomalies.sort_values(by="anomaly_score", ascending=True).head(30)

    return anomalies