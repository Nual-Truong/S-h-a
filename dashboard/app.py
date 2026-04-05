import streamlit as st
import pandas as pd
import os
import subprocess
from pathlib import Path
from db.database import get_connection
from etl.extract import extract_csv, extract_excel, save_csv_from_dataframe
from etl.load import load_to_db
from etl.transform import transform_data
from forecast.revenue_forecast import evaluate_forecast, forecast_next_month
from ai.trend_analysis import analyze_trend
from ai.anomaly_detection import detect_anomalies
from blockchain.ledger import (
    get_recent_anchor_logs,
    get_recent_audit_logs,
    tamper_random_transaction,
    verify_ledger,
)


def fmt_number(value):
    return f"{int(value):,}"


def format_columns_with_commas(dataframe: pd.DataFrame, columns):
    output = dataframe.copy()
    for col in columns:
        if col in output.columns:
            output[col] = output[col].apply(lambda v: f"{int(v):,}" if pd.notna(v) else v)
    return output


def open_local_path(path_value: str):
    target = Path(path_value).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Không tìm thấy đường dẫn: {target}")

    if os.name == "nt":
        os.startfile(str(target))
        return

    if os.name == "posix":
        if "darwin" in os.uname().sysname.lower():
            subprocess.run(["open", str(target)], check=True)
        else:
            subprocess.run(["xdg-open", str(target)], check=True)
        return

    raise OSError("Hệ điều hành hiện tại chưa được hỗ trợ mở đường dẫn tự động.")

st.title("Quản Lý Tài Chính Thông Minh")

# ======================
# LOAD DATA
# ======================
conn = get_connection()
df = pd.read_sql("SELECT * FROM transactions", conn)
conn.close()

with get_connection() as integrity_conn:
    integrity_result = verify_ledger(integrity_conn, auto_rebuild=True)
    audit_df = get_recent_audit_logs(integrity_conn, limit=8)
    anchor_df = get_recent_anchor_logs(integrity_conn, limit=8)

latest_hash = integrity_result["latest_hash"]
latest_security_id = integrity_result.get("latest_security_id")
merkle_root = integrity_result.get("merkle_root")
anchor_hash = integrity_result.get("anchor_hash")
short_hash = "N/A"
short_security_id = "N/A"
short_merkle_root = "N/A"
short_anchor_hash = "N/A"
if latest_hash:
    short_hash = f"{latest_hash[:12]}...{latest_hash[-12:]}"
if latest_security_id:
    short_security_id = latest_security_id
if merkle_root:
    short_merkle_root = f"{merkle_root[:12]}...{merkle_root[-12:]}"
if anchor_hash:
    short_anchor_hash = f"{anchor_hash[:12]}...{anchor_hash[-12:]}"

# ======================
# BASIC METRICS
# ======================
st.metric("Tổng doanh thu", fmt_number(df["amount"].sum()))
st.metric("Tổng chi phí", fmt_number(df["cost"].sum()))
st.metric("Tổng lợi nhuận", fmt_number(df["profit"].sum()))

# ======================
# REVENUE CHART
# ======================
import altair as alt

st.subheader("📊 Hiển thị dữ liệu doanh thu tháng tới qua AI")

# TẠO chart_data trước khi dùng
chart_data = df.groupby("date")["amount"].mean().reset_index()
chart_data = chart_data.sort_values("date")
chart_data["amount_smooth"] = chart_data["amount"].rolling(window=14, min_periods=1).mean()

chart = alt.Chart(chart_data).mark_line(
    point=alt.OverlayMarkDef(size=40, opacity=0.65)
).encode(
    x="date:T",
    y=alt.Y("amount_smooth:Q", title="amount"),
    tooltip=[
        alt.Tooltip("date:T", title="Ngày"),
        alt.Tooltip("amount:Q", title="Doanh thu TB ngày", format=",.0f"),
        alt.Tooltip("amount_smooth:Q", title="Doanh thu làm mượt", format=",.0f"),
    ],
).interactive()

st.altair_chart(chart, width="stretch")

# ======================
# FORECAST
# ======================
forecast = forecast_next_month()
st.subheader("Dự báo doanh thu tháng tới")
st.success(f"{fmt_number(forecast)} VND")

# ======================
# ANOMALY DETECTION (AI)
# ======================
anomalies = detect_anomalies()
anomaly_count = len(anomalies)

st.metric("Phát hiện bất thường", anomaly_count)

# ======================
# TREND ANALYSIS
# ======================
st.subheader("Phân tích xu hướng tiêu dùng")
trend_df = analyze_trend()
trend_display = trend_df.rename(
    columns={
        "date": "Tháng",
        "category": "Danh mục",
        "amount": "Doanh thu",
    }
)
trend_display = format_columns_with_commas(trend_display, ["Doanh thu"])
st.dataframe(
    trend_display,
    width="stretch",
)

# ======================
# RISK ALERT
# ======================
st.subheader("Cảnh báo rủi ro tài chính")

if anomalies.empty:
    st.success("Không phát hiện rủi ro tài chính")
else:
    st.warning(f"{len(anomalies)} Phát hiện giao dịch đáng ngờ")
    anomalies_display = anomalies.rename(
        columns={
            "date": "Ngày",
            "category": "Danh mục",
            "amount": "Doanh thu",
            "cost": "Chi phí",
            "profit": "Lợi nhuận",
            "anomaly": "Nhãn bất thường",
            "anomaly_reason": "Lý do bất thường",
        }
    )
    anomalies_display = format_columns_with_commas(
        anomalies_display,
        ["Doanh thu", "Chi phí", "Lợi nhuận"],
    )
    st.dataframe(
        anomalies_display,
        width="stretch",
    )

from forecast.revenue_forecast import forecast_by_category

st.subheader("🔮 Dự báo theo danh mục")
forecast_df = forecast_by_category()
forecast_display = forecast_df.sort_values(by="Forecast", ascending=False).rename(
    columns={"Category": "Danh mục", "Forecast": "Dự báo doanh thu"}
)
forecast_display = format_columns_with_commas(forecast_display, ["Dự báo doanh thu"])
st.dataframe(
    forecast_display,
    width="stretch",
)

forecast_eval = evaluate_forecast()
st.caption("Đánh giá chất lượng mô hình dự báo")
if forecast_eval["mae"] is None or forecast_eval["mape"] is None:
    st.info("Chưa đủ dữ liệu để tính MAE/MAPE (cần ít nhất 3 mốc tháng và doanh thu khác 0).")
else:
    col1, col2 = st.columns(2)
    col1.metric("MAE", f"{forecast_eval['mae']:.2f}")
    col2.metric("MAPE", f"{forecast_eval['mape']:.2f}%")

from ai.insight_generator import generate_insight

st.subheader("🤖 Thông tin tài chính từ AI")
st.info(generate_insight())

from ai.seasonality import analyze_seasonality

st.subheader("📈 Phân tích tính chu kỳ/mùa vụ")
season_df = analyze_seasonality()
st.bar_chart(season_df.set_index("month"))

# ======================
# BLOCKCHAIN INTEGRITY CHECK
# ======================
st.subheader("Toàn vẹn dữ liệu Blockchain")

st.subheader("Tóm tắt Blockchain")
card1, card2, card3 = st.columns(3)

ecdsa_status = "Hợp lệ" if not any("Chữ ký số" in issue for issue in integrity_result["issues"]) else "Lỗi xác minh"
card1.metric("ECDSA Signature", ecdsa_status)
card2.metric("Merkle Root", short_merkle_root)
card3.metric("Anchor Snapshot", short_anchor_hash)

st.caption(f"Security ID mới nhất: {short_security_id}")
st.caption(f"Hash mới nhất: {short_hash}")

if integrity_result["valid"]:
    st.success("Sổ cái hợp lệ. Dữ liệu tài chính đã được bảo vệ khỏi chỉnh sửa ngầm.")
    if integrity_result["issues"]:
        st.info(integrity_result["issues"][0])
else:
    st.error("Xác minh sổ cái thất bại.")
    if integrity_result.get("first_mismatch_block") is not None:
        st.warning(f"Khối bị lệch đầu tiên: {integrity_result['first_mismatch_block']}")
    preview_issues = integrity_result["issues"][:3]
    for issue in preview_issues:
        st.write(f"- {issue}")
    if len(integrity_result["issues"]) > 3:
        st.caption(f"... và {len(integrity_result['issues']) - 3} lỗi khác")

st.caption(f"Số khối: {integrity_result['blocks']}")
st.caption(f"Hash mới nhất: {short_hash}")
st.caption(f"Security ID mới nhất: {short_security_id}")
st.caption(f"Merkle root: {short_merkle_root}")
st.caption(f"Anchor hash mới nhất: {short_anchor_hash}")

with st.expander("Xem chi tiết blockchain"):
    st.write(f"Hash đầy đủ: {latest_hash}")
    st.write(f"Security ID đầy đủ: {latest_security_id}")
    st.write(f"Merkle root đầy đủ: {merkle_root}")
    st.write(f"Anchor hash đầy đủ: {anchor_hash}")
    if integrity_result["issues"]:
        st.write("Danh sách chi tiết vấn đề:")
        for issue in integrity_result["issues"]:
            st.write(f"- {issue}")

status_map = {"PASSED": "THÀNH CÔNG", "FAILED": "THẤT BẠI"}
audit_display = audit_df.copy()
if not audit_display.empty:
    audit_display["status"] = audit_display["status"].map(status_map).fillna(audit_display["status"])

st.caption("Lịch sử xác minh blockchain gần nhất")
st.dataframe(
    audit_display.rename(
        columns={
            "checked_at": "Thời gian",
            "status": "Trạng thái",
            "blocks": "Số khối",
            "latest_hash": "Hash mới nhất",
            "latest_security_id": "Security ID mới nhất",
            "issue_count": "Số lỗi",
            "issue_preview": "Tóm tắt lỗi",
        }
    ),
    width="stretch",
)

st.caption("Lịch sử neo hash (anchor snapshot) gần nhất")
st.dataframe(
    anchor_df.rename(
        columns={
            "anchored_at": "Thời gian neo",
            "latest_hash": "Hash khối",
            "merkle_root": "Merkle root",
            "anchor_hash": "Anchor hash",
            "note": "Ghi chú",
        }
    ),
    width="stretch",
)

st.divider()
st.subheader("Kiểm thử giả lập chỉnh sửa (Demo)")
st.caption("Chỉ dùng để demo. Chức năng này sẽ cố ý sửa một bản ghi.")

if st.button("Giả lập sửa ngẫu nhiên 1 giao dịch"):
    with get_connection() as tamper_conn:
        tamper_info = tamper_random_transaction(tamper_conn)

    if tamper_info is None:
        st.warning("Không tìm thấy giao dịch để giả lập chỉnh sửa.")
    else:
        st.warning(
            f"Đã chỉnh sửa dòng {tamper_info['rowid']}: số tiền {tamper_info['old_amount']} -> {tamper_info['new_amount']}"
        )
        st.info("Đang tải lại để cập nhật trạng thái blockchain...")
        st.rerun()

if st.button("Khôi phục dữ liệu sau demo"):
    try:
        baseline_df = extract_csv("data/transactions.csv")
        baseline_clean_df = transform_data(baseline_df)
        load_to_db(baseline_clean_df)
        st.success("Đã khôi phục dữ liệu từ CSV gốc và rebuild blockchain thành công.")
        st.rerun()
    except Exception as exc:
        st.error(f"Khôi phục thất bại: {exc}")

st.divider()
st.subheader("Phân tích dữ liệu từ file Excel")
st.caption("Nhập đường dẫn file Excel (.xlsx/.xls), hệ thống sẽ chuyển sang CSV và phân tích ngay.")

excel_path = st.text_input("Đường dẫn file Excel", value="")
path_to_open = st.text_input("Mở nhanh đường dẫn bất kỳ trên máy", value="")

if st.button("Mở đường dẫn trên máy"):
    try:
        open_local_path(path_to_open.strip())
        st.success("Đã gửi yêu cầu mở đường dẫn trên máy.")
    except Exception as exc:
        st.error(f"Không thể mở đường dẫn: {exc}")

if st.button("Chuyển Excel sang CSV và phân tích"):
    try:
        excel_df = extract_excel(excel_path.strip())
        csv_ready_df = transform_data(excel_df)
        csv_path = save_csv_from_dataframe(csv_ready_df, excel_path.strip())

        st.success(f"Đã chuyển đổi thành công sang CSV: {csv_path}")

        if st.button("Mở file CSV vừa tạo"):
            try:
                open_local_path(csv_path)
                st.success("Đã mở file CSV trên máy.")
            except Exception as exc:
                st.error(f"Không thể mở file CSV: {exc}")

        if st.button("Mở thư mục chứa CSV"):
            try:
                open_local_path(str(Path(csv_path).parent))
                st.success("Đã mở thư mục chứa CSV trên máy.")
            except Exception as exc:
                st.error(f"Không thể mở thư mục CSV: {exc}")

        st.metric("Tổng doanh thu (CSV)", int(csv_ready_df["amount"].sum()))
        st.metric("Tổng chi phí (CSV)", int(csv_ready_df["cost"].sum()))
        st.metric("Tổng lợi nhuận (CSV)", int(csv_ready_df["profit"].sum()))

        csv_chart_data = csv_ready_df.groupby("date")["amount"].mean().reset_index()
        csv_chart_data = csv_chart_data.sort_values("date")
        csv_chart_data["amount_smooth"] = csv_chart_data["amount"].rolling(window=14, min_periods=1).mean()
        csv_chart = alt.Chart(csv_chart_data).mark_line(
            point=alt.OverlayMarkDef(size=40, opacity=0.65)
        ).encode(
            x="date:T",
            y=alt.Y("amount_smooth:Q", title="amount"),
            tooltip=[
                alt.Tooltip("date:T", title="Ngày"),
                alt.Tooltip("amount:Q", title="Doanh thu TB ngày", format=",.0f"),
                alt.Tooltip("amount_smooth:Q", title="Doanh thu làm mượt", format=",.0f"),
            ],
        ).interactive()
        st.altair_chart(csv_chart, width="stretch")

        category_summary = (
            csv_ready_df.groupby("category")[["amount", "cost", "profit"]]
            .sum()
            .reset_index()
            .rename(
                columns={
                    "category": "Danh mục",
                    "amount": "Doanh thu",
                    "cost": "Chi phí",
                    "profit": "Lợi nhuận",
                }
            )
        )
        st.dataframe(category_summary, width="stretch")
    except Exception as exc:
        st.error(f"Không thể xử lý file Excel: {exc}")