import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from db.database import get_connection


def _load_monthly_revenue():
    with get_connection() as conn:
        df = pd.read_sql("SELECT date, amount FROM transactions", conn)

    if df.empty:
        return pd.DataFrame(columns=["month", "amount", "month_num"])

    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    monthly = df.groupby("month")["amount"].sum().reset_index()
    monthly["month_num"] = range(len(monthly))
    return monthly


def _forecast_next_value_arima(series: pd.Series):
    values = series.astype(float).tolist()

    if len(values) < 2:
        return 0.0

    if len(values) < 4:
        # Fallback for very short history where ARIMA is unstable.
        return float(values[-1])

    try:
        model = ARIMA(values, order=(1, 1, 1))
        fitted = model.fit()
        return float(fitted.forecast(steps=1)[0])
    except Exception:
        return float(values[-1])


def _evaluate_arima_in_sample(series: pd.Series):
    values = series.astype(float).tolist()

    if len(values) < 4:
        return {"mae": None, "mape": None, "samples": len(values)}

    try:
        model = ARIMA(values, order=(1, 1, 1))
        fitted = model.fit()
        predictions = fitted.predict(start=1, end=len(values) - 1)
        actual = pd.Series(values[1:], dtype="float64")
        predicted = pd.Series(predictions, dtype="float64")

        abs_error = (actual - predicted).abs()
        mae = float(abs_error.mean())

        non_zero = actual != 0
        if non_zero.any():
            mape = float((abs_error[non_zero] / actual[non_zero]).mean() * 100)
        else:
            mape = None

        return {
            "mae": mae,
            "mape": mape,
            "samples": len(values),
        }
    except Exception:
        return {"mae": None, "mape": None, "samples": len(values)}


def forecast_next_month():
    monthly = _load_monthly_revenue()

    forecast = _forecast_next_value_arima(monthly["amount"])
    return int(max(0, forecast))


def evaluate_forecast():
    monthly = _load_monthly_revenue()
    return _evaluate_arima_in_sample(monthly["amount"])


def forecast_by_category():
    with get_connection() as conn:
        df = pd.read_sql("SELECT date, category, amount FROM transactions", conn)

    if df.empty:
        return pd.DataFrame(columns=["Category", "Forecast"])

    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    results = []

    for category in df["category"].unique():
        sub = df[df["category"] == category]
        monthly = sub.groupby("month")["amount"].sum().reset_index()
        if len(monthly) < 2:
            continue

        forecast = _forecast_next_value_arima(monthly["amount"])

        results.append((category, int(max(0, forecast))))

    return pd.DataFrame(results, columns=["Category", "Forecast"])
