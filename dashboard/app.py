import json
import os
import re
import subprocess
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from config import (
    APP_MODE,
    DASHBOARD_ADMIN_PASSWORD,
    DASHBOARD_VIEWER_LABEL,
    ENABLE_LEGACY_BLOCKCHAIN,
    FABRIC_HASH_MODE,
)
from db.database import get_connection
from etl.extract import extract_csv, extract_excel, save_csv_from_dataframe
from etl.load import load_to_db
from etl.transform import transform_data
from fabric.sync import (
    append_runtime_log,
    clear_fabric_checkpoint,
    get_fabric_checkpoint,
    get_fabric_status,
    get_recent_runtime_logs,
    run_fabric_client,
    save_fabric_checkpoint,
    summarize_fabric_outbox,
)
from forecast.revenue_forecast import evaluate_forecast, forecast_by_category, forecast_next_month
from ai.anomaly_detection import detect_anomalies
from ai.insight_generator import generate_insight
from ai.seasonality import analyze_seasonality
from ai.trend_analysis import analyze_trend
from services.reporting import build_excel_report_bytes, build_pdf_report_bytes

st.set_page_config(
    page_title="Quản Lý Tài Chính Thông Minh",
    page_icon="📊",
    layout="wide",
)

if ENABLE_LEGACY_BLOCKCHAIN:
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


def resolve_dashboard_role() -> str:
    if "dashboard_role" not in st.session_state:
        st.session_state["dashboard_role"] = "viewer"

    if not DASHBOARD_ADMIN_PASSWORD:
        st.session_state["dashboard_role"] = "admin"
        return "admin"

    with st.sidebar.form("dashboard_access_form"):
        st.caption(f"Vai trò hiện tại: {st.session_state['dashboard_role']}")
        password = st.text_input("Mật khẩu quản trị", type="password")
        submitted = st.form_submit_button("Đăng nhập")

    if submitted:
        if password == DASHBOARD_ADMIN_PASSWORD:
            st.session_state["dashboard_role"] = "admin"
            st.sidebar.success("Đăng nhập quản trị thành công.")
            st.rerun()
        else:
            st.sidebar.error("Sai mật khẩu quản trị.")

    if st.session_state["dashboard_role"] == "admin":
        st.sidebar.success("Đang ở chế độ quản trị.")
    else:
        st.sidebar.info(f"Chế độ xem: {DASHBOARD_VIEWER_LABEL}")

    return st.session_state["dashboard_role"]


dashboard_role = resolve_dashboard_role()
is_admin = dashboard_role == "admin"


def _strip_ansi(value: str) -> str:
    ansi_pattern = r"\x1B\[[0-?]*[ -/]*[@-~]"
    return re.sub(ansi_pattern, "", value)


def parse_fabric_message(raw_message: str) -> dict:
    cleaned = _strip_ansi(str(raw_message or "")).strip()
    output = {
        "cleaned": cleaned,
        "progress_done": None,
        "progress_total": None,
        "json": None,
    }

    if not cleaned:
        return output

    progress_matches = re.findall(r"Progress:\s*(\d+)\s*/\s*(\d+)", cleaned, flags=re.IGNORECASE)
    if progress_matches:
        done, total = progress_matches[-1]
        output["progress_done"] = int(done)
        output["progress_total"] = int(total)

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate_text = cleaned[first_brace : last_brace + 1]
        try:
            payload = json.loads(candidate_text)
            if isinstance(payload, dict):
                output["json"] = payload
        except Exception:
            pass

    return output


def render_fabric_message(raw_message: str):
    parsed = parse_fabric_message(raw_message)
    cleaned = parsed["cleaned"]

    if not cleaned:
        return

    progress_lines = [line for line in cleaned.splitlines() if line.strip().lower().startswith("progress:")]
    for line in progress_lines:
        st.caption(line.strip())

    progress_done = parsed.get("progress_done")
    progress_total = parsed.get("progress_total")
    if progress_done is not None and progress_total and progress_total > 0:
        st.progress(min(max(progress_done / progress_total, 0), 1))

    payload = parsed.get("json")
    if not payload:
        st.info(cleaned)
        return

    if payload.get("message"):
        st.success(payload.get("message"))

    if payload.get("count") is not None:
        st.caption(f"Số asset submit thành công: {payload.get('count')}")

    if payload.get("sample_count") is not None:
        st.caption(f"Đang hiển thị mẫu: {payload.get('sample_count')} giao dịch đầu")

    rows = []
    results = payload.get("sample_results") or payload.get("results") or []
    for item in results:
        asset_id = item.get("assetId")
        response_raw = item.get("response")
        response_obj = None
        if isinstance(response_raw, str):
            try:
                response_obj = json.loads(response_raw)
            except Exception:
                response_obj = None

        if isinstance(response_obj, dict):
            row_payload = response_obj.get("payload", {}) or {}
            rows.append(
                {
                    "asset_id": asset_id,
                    "category": row_payload.get("category"),
                    "amount": row_payload.get("amount"),
                    "cost": row_payload.get("cost"),
                    "profit": row_payload.get("profit"),
                    "updated_at": response_obj.get("updatedAt"),
                }
            )
        else:
            rows.append(
                {
                    "asset_id": asset_id,
                    "category": None,
                    "amount": None,
                    "cost": None,
                    "profit": None,
                    "updated_at": None,
                }
            )

    if rows:
        result_df = pd.DataFrame(rows)
        result_df = format_columns_with_commas(result_df, ["amount", "cost", "profit"])
        st.dataframe(result_df, width="stretch")

    with st.expander("Raw Fabric message"):
        st.code(cleaned)


def run_fabric_auto_resume(total_assets: int, start_offset: int, batch_size: int, commit_timeout: int):
    previous_env = {
        "FABRIC_START_OFFSET": os.environ.get("FABRIC_START_OFFSET"),
        "FABRIC_MAX_ASSETS": os.environ.get("FABRIC_MAX_ASSETS"),
        "FABRIC_COMMIT_TIMEOUT": os.environ.get("FABRIC_COMMIT_TIMEOUT"),
    }

    progress_bar = st.progress(0.0)
    status_box = st.empty()
    completed = 0
    batches = 0
    stopped_reason = None

    try:
        for offset in range(start_offset, total_assets, batch_size):
            current_batch_size = min(batch_size, total_assets - offset)
            os.environ["FABRIC_START_OFFSET"] = str(offset)
            os.environ["FABRIC_MAX_ASSETS"] = str(current_batch_size)
            os.environ["FABRIC_COMMIT_TIMEOUT"] = str(commit_timeout)

            batches += 1
            status_box.info(
                f"Đang chạy batch {batches}: offset={offset}, size={current_batch_size}, timeout={commit_timeout}s"
            )

            sync_result = run_fabric_client()
            parsed = parse_fabric_message(sync_result.get("message", ""))
            payload = parsed.get("json") or {}
            submitted_count = payload.get("count") or sync_result.get("count") or current_batch_size

            completed = min(total_assets - start_offset, completed + int(submitted_count))
            denominator = max(total_assets - start_offset, 1)
            progress_bar.progress(min(max(completed / denominator, 0), 1))

            save_fabric_checkpoint(
                {
                    "status": "running",
                    "next_offset": offset + int(submitted_count),
                    "completed": completed,
                    "target": max(total_assets - start_offset, 0),
                    "batch_size": batch_size,
                    "commit_timeout": commit_timeout,
                    "last_message": sync_result.get("message"),
                }
            )

            if sync_result.get("status") in {"error", "dry_run"}:
                stopped_reason = sync_result.get("message", "Không rõ lỗi")
                save_fabric_checkpoint(
                    {
                        "status": "stopped",
                        "next_offset": offset,
                        "completed": completed,
                        "target": max(total_assets - start_offset, 0),
                        "batch_size": batch_size,
                        "commit_timeout": commit_timeout,
                        "last_message": stopped_reason,
                    }
                )
                break

        final_status = "completed" if stopped_reason is None else "stopped"
        if final_status == "completed":
            save_fabric_checkpoint(
                {
                    "status": "completed",
                    "next_offset": total_assets,
                    "completed": max(total_assets - start_offset, 0),
                    "target": max(total_assets - start_offset, 0),
                    "batch_size": batch_size,
                    "commit_timeout": commit_timeout,
                    "last_message": "Hoàn tất auto-resume theo lô.",
                }
            )
        return {
            "status": final_status,
            "completed": completed,
            "target": max(total_assets - start_offset, 0),
            "batches": batches,
            "reason": stopped_reason,
        }
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def inject_custom_css():
    st.markdown(
        """
        <style>
        .main > div {
            padding-top: 1.2rem;
        }
        .block-container {
            max-width: 1400px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_custom_css()
st.title("Quản Lý Tài Chính Thông Minh")
st.caption("Dashboard tài chính + Fabric-first sync với khả năng theo dõi trạng thái và hash toàn vẹn.")

tab_overview, tab_fabric, tab_excel = st.tabs(["📈 Tổng quan", "🔗 Fabric", "📄 Excel"])

conn = get_connection()
df = pd.read_sql("SELECT * FROM transactions", conn)
conn.close()

if not df.empty and "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

with get_connection() as integrity_conn:
    if ENABLE_LEGACY_BLOCKCHAIN:
        integrity_result = verify_ledger(integrity_conn, auto_rebuild=True)
        audit_df = get_recent_audit_logs(integrity_conn, limit=8)
        anchor_df = get_recent_anchor_logs(integrity_conn, limit=8)
    else:
        integrity_result = None
        audit_df = pd.DataFrame()
        anchor_df = pd.DataFrame()

fabric_status = get_fabric_status()
fabric_integrity = summarize_fabric_outbox()
fabric_checkpoint = get_fabric_checkpoint()

st.sidebar.header("Bộ lọc hiển thị")

if not df.empty and df["date"].notna().any():
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.sidebar.date_input(
        "Khoảng ngày",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    else:
        start_date, end_date = pd.to_datetime(min_date), pd.to_datetime(max_date)
else:
    start_date = end_date = None

categories = sorted([c for c in df.get("category", pd.Series(dtype=str)).dropna().unique().tolist()])
selected_categories = st.sidebar.multiselect("Danh mục", options=categories, default=categories)

df_view = df.copy()
if start_date is not None and end_date is not None and "date" in df_view.columns:
    df_view = df_view[(df_view["date"] >= start_date) & (df_view["date"] <= end_date)]
if selected_categories and "category" in df_view.columns:
    df_view = df_view[df_view["category"].isin(selected_categories)]

st.sidebar.caption(f"Số dòng sau lọc: {len(df_view):,}")
st.sidebar.caption(f"Fabric status: {fabric_status.get('status', 'not_synced')}")
use_filtered_ai_views = st.sidebar.toggle(
    "Áp bộ lọc cho bảng AI",
    value=True,
    help="Bật để bảng Xu hướng và Cảnh báo dùng dữ liệu sau lọc ở sidebar.",
)

with tab_overview:
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Tổng doanh thu", fmt_number(df_view["amount"].sum() if not df_view.empty else 0))
    metric_col2.metric("Tổng chi phí", fmt_number(df_view["cost"].sum() if not df_view.empty else 0))
    metric_col3.metric("Tổng lợi nhuận", fmt_number(df_view["profit"].sum() if not df_view.empty else 0))
    st.caption("Các KPI phía trên đang theo bộ lọc sidebar.")

    st.subheader("📊 Hiển thị dữ liệu doanh thu tháng tới qua AI")
    if df_view.empty:
        st.warning("Không có dữ liệu theo bộ lọc hiện tại để vẽ biểu đồ.")
    else:
        chart_data = df_view.groupby("date")["amount"].mean().reset_index().sort_values("date")
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

    forecast = forecast_next_month()
    st.subheader("Dự báo doanh thu tháng tới")
    st.success(f"{fmt_number(forecast)} VND")

    anomalies = detect_anomalies()
    st.metric("Phát hiện bất thường", len(anomalies))

    st.subheader("Phân tích xu hướng tiêu dùng")
    if use_filtered_ai_views:
        if df_view.empty:
            trend_df = pd.DataFrame(columns=["date", "category", "amount"])
        else:
            trend_df = (
                df_view.dropna(subset=["date", "category", "amount"])
                .assign(date=lambda x: x["date"].dt.to_period("M").dt.to_timestamp())
                .groupby(["date", "category"], as_index=False)["amount"]
                .sum()
            )
    else:
        trend_df = analyze_trend()

    trend_display = trend_df.rename(columns={"date": "Tháng", "category": "Danh mục", "amount": "Doanh thu"})
    trend_display = format_columns_with_commas(trend_display, ["Doanh thu"])
    st.dataframe(trend_display, width="stretch")

    st.subheader("Cảnh báo rủi ro tài chính")
    anomalies_view = anomalies.copy()
    if use_filtered_ai_views and not anomalies_view.empty:
        if start_date is not None and end_date is not None and "date" in anomalies_view.columns:
            anomalies_view["date"] = pd.to_datetime(anomalies_view["date"], errors="coerce")
            anomalies_view = anomalies_view[
                (anomalies_view["date"] >= start_date) & (anomalies_view["date"] <= end_date)
            ]
        if selected_categories and "category" in anomalies_view.columns:
            anomalies_view = anomalies_view[anomalies_view["category"].isin(selected_categories)]

    if anomalies_view.empty:
        st.success("Không phát hiện rủi ro tài chính")
    else:
        st.warning(f"{len(anomalies_view)} phát hiện giao dịch đáng ngờ")
        anomalies_display = anomalies_view.rename(
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
        anomalies_display = format_columns_with_commas(anomalies_display, ["Doanh thu", "Chi phí", "Lợi nhuận"])
        st.dataframe(anomalies_display, width="stretch")

    st.subheader("🔮 Dự báo theo danh mục")
    forecast_df = forecast_by_category()
    forecast_display = forecast_df.sort_values(by="Forecast", ascending=False).rename(
        columns={"Category": "Danh mục", "Forecast": "Dự báo doanh thu"}
    )
    forecast_display = format_columns_with_commas(forecast_display, ["Dự báo doanh thu"])
    st.dataframe(forecast_display, width="stretch")

    forecast_eval = evaluate_forecast()
    st.caption("Đánh giá chất lượng mô hình dự báo")
    if forecast_eval["mae"] is None or forecast_eval["mape"] is None:
        st.info("Chưa đủ dữ liệu để tính MAE/MAPE (cần ít nhất 3 mốc tháng và doanh thu khác 0).")
    else:
        score_col1, score_col2 = st.columns(2)
        score_col1.metric("MAE", f"{forecast_eval['mae']:.2f}")
        score_col2.metric("MAPE", f"{forecast_eval['mape']:.2f}%")

    st.subheader("🤖 Thông tin tài chính từ AI")
    st.info(generate_insight())

    st.subheader("📈 Phân tích tính chu kỳ/mùa vụ")
    season_df = analyze_seasonality()
    st.bar_chart(season_df.set_index("month"))

    report_sections = {
        "overview": df_view,
        "trend": trend_display,
        "anomalies": anomalies_display if "anomalies_display" in locals() else pd.DataFrame(),
        "forecast": forecast_display,
        "seasonality": season_df,
    }
    report_bytes = build_excel_report_bytes(report_sections)
    report_pdf_bytes = build_pdf_report_bytes(
        "Financial Dashboard Report",
        report_sections,
        subtitle="Báo cáo tổng hợp từ dữ liệu đang hiển thị trên dashboard.",
    )
    report_col1, report_col2, report_col3 = st.columns(3)
    report_col1.download_button(
        "Tải báo cáo Excel",
        data=report_bytes,
        file_name="financial_dashboard_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    report_col2.download_button(
        "Tải báo cáo PDF",
        data=report_pdf_bytes,
        file_name="financial_dashboard_report.pdf",
        mime="application/pdf",
    )
    report_col3.caption("Báo cáo gồm dữ liệu tổng quan, xu hướng, cảnh báo, dự báo và mùa vụ.")

with tab_fabric:
    st.subheader("Fabric-First Status")
    st.caption(f"App mode: {APP_MODE}")

    parsed_status = parse_fabric_message(fabric_status.get("message", ""))
    parsed_payload = parsed_status.get("json") or {}

    total_assets = int(fabric_integrity.get("asset_count") or 0)
    batch_count = int(parsed_payload.get("count") or 0)
    last_offset = int(parsed_payload.get("start_offset") or 0)
    estimated_synced = min(total_assets, last_offset + batch_count)

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    fcol1.metric("Fabric status", fabric_status.get("status", "not_synced"))
    fcol2.metric("Tổng outbox", total_assets)
    fcol3.metric("Đồng bộ gần nhất", batch_count)
    fcol4.metric("Ước lượng đã sync", estimated_synced)

    if total_assets > 0:
        st.progress(min(max((estimated_synced / total_assets), 0), 1))
        st.caption(f"Tiến độ tổng thể (ước lượng): {estimated_synced}/{total_assets}")

    if fabric_status.get("updated_at"):
        st.caption(f"Đồng bộ lúc: {fabric_status.get('updated_at')}")

    if fabric_status.get("payload_path"):
        st.caption(f"Fabric payload: {fabric_status['payload_path']}")

    st.caption(f"Hash mode: {fabric_integrity.get('hash_mode') or FABRIC_HASH_MODE}")

    if fabric_status.get("message"):
        render_fabric_message(fabric_status["message"])

    st.markdown("**Cấu hình hash mode**")
    hash_mode_options = {
        "total": "Hash tổng payload",
        "per-transaction": "Hash riêng từng giao dịch",
        "both": "Bật cả hash tổng và hash riêng",
    }
    current_mode = fabric_integrity.get("hash_mode") or FABRIC_HASH_MODE
    default_mode_index = list(hash_mode_options.keys()).index(current_mode) if current_mode in hash_mode_options else 0
    selected_hash_mode = st.selectbox(
        "Chọn hash mode",
        options=list(hash_mode_options.keys()),
        index=default_mode_index,
        format_func=lambda key: f"{key} - {hash_mode_options[key]}",
    )

    if st.button("Áp dụng hash mode và chạy ETL", disabled=not is_admin):
        try:
            os.environ["FABRIC_HASH_MODE"] = selected_hash_mode
            baseline_df = extract_csv("data/transactions.csv")
            baseline_clean_df = transform_data(baseline_df)
            load_to_db(baseline_clean_df)
            st.success(f"Đã áp dụng FABRIC_HASH_MODE={selected_hash_mode} và chạy ETL thành công.")
            st.rerun()
        except Exception as exc:
            st.error(f"Không thể áp dụng hash mode: {exc}")
    if not is_admin:
        st.caption("Cần đăng nhập quản trị để đổi hash mode và chạy ETL.")

    st.markdown("**Chạy auto-resume theo lô**")
    batch_col1, batch_col2, batch_col3 = st.columns(3)
    batch_size = batch_col1.number_input("Kích thước batch", min_value=10, max_value=2000, value=300, step=10)
    commit_timeout = batch_col2.number_input("Commit timeout (giây)", min_value=60, max_value=3600, value=900, step=30)
    checkpoint_next_offset = int(fabric_checkpoint.get("next_offset") or 0)
    default_start_offset = checkpoint_next_offset if checkpoint_next_offset > 0 else min(estimated_synced, total_assets)
    start_offset_input = batch_col3.number_input(
        "Offset bắt đầu", min_value=0, max_value=max(total_assets, 0), value=min(default_start_offset, total_assets), step=1
    )

    st.caption(
        f"Checkpoint hiện tại: status={fabric_checkpoint.get('status')}, next_offset={fabric_checkpoint.get('next_offset')}, completed={fabric_checkpoint.get('completed')}"
    )

    checkpoint_clear_col, _ = st.columns([1, 3])
    if checkpoint_clear_col.button("Xóa checkpoint auto-resume", disabled=not is_admin):
        clear_fabric_checkpoint()
        st.success("Đã xóa checkpoint auto-resume.")
        st.rerun()

    if st.button("Auto-resume sync toàn bộ", disabled=not is_admin):
        if total_assets <= 0:
            st.warning("Chưa có dữ liệu outbox để đồng bộ.")
        else:
            summary = run_fabric_auto_resume(
                total_assets=total_assets,
                start_offset=int(start_offset_input),
                batch_size=int(batch_size),
                commit_timeout=int(commit_timeout),
            )
            if summary["status"] == "completed":
                st.success(
                    f"Hoàn tất auto-resume: {summary['completed']}/{summary['target']} giao dịch qua {summary['batches']} batch."
                )
            else:
                st.error(
                    f"Auto-resume dừng giữa chừng: {summary['completed']}/{summary['target']} qua {summary['batches']} batch."
                )
                st.code(summary.get("reason") or "Không rõ lỗi")
            st.rerun()
    if not is_admin:
        st.caption("Cần đăng nhập quản trị để chạy auto-resume hoặc xóa checkpoint.")

    if fabric_integrity.get("payload_hash"):
        hash_value = fabric_integrity["payload_hash"]
        st.caption(f"Payload hash: {hash_value[:12]}...{hash_value[-12:]}")

    if fabric_integrity.get("transaction_hash_count"):
        st.caption(f"Transaction hash count: {fabric_integrity['transaction_hash_count']}")
        hash_rows = fabric_integrity.get("transaction_hash_samples") or []
        if hash_rows:
            hash_df = pd.DataFrame(hash_rows)
            hash_df["transaction_hash"] = hash_df["transaction_hash"].apply(
                lambda h: f"{h[:12]}...{h[-12:]}" if isinstance(h, str) and len(h) > 24 else h
            )
            st.dataframe(hash_df, width="stretch")

    if fabric_integrity["valid"]:
        st.success("Outbox Fabric hợp lệ và sẵn sàng để submit vào chaincode.")
    else:
        st.warning("Outbox Fabric chưa sẵn sàng.")
        for issue in fabric_integrity["issues"]:
            st.write(f"- {issue}")

    st.subheader("Nhật ký chạy gần nhất")
    recent_logs = get_recent_runtime_logs(limit=15)
    if recent_logs:
        logs_df = pd.DataFrame(recent_logs)
        logs_df["message"] = logs_df["message"].astype(str).str.slice(0, 140)
        st.dataframe(logs_df[["timestamp", "component", "status", "message"]], width="stretch")
    else:
        st.info("Chưa có nhật ký chạy nào.")

if ENABLE_LEGACY_BLOCKCHAIN and integrity_result is not None:
    st.divider()
    st.subheader("Legacy Blockchain (Optional)")

    latest_hash = integrity_result["latest_hash"]
    latest_security_id = integrity_result.get("latest_security_id")
    merkle_root = integrity_result.get("merkle_root")
    anchor_hash = integrity_result.get("anchor_hash")

    short_hash = f"{latest_hash[:12]}...{latest_hash[-12:]}" if latest_hash else "N/A"
    short_security_id = latest_security_id if latest_security_id else "N/A"
    short_merkle_root = f"{merkle_root[:12]}...{merkle_root[-12:]}" if merkle_root else "N/A"
    short_anchor_hash = f"{anchor_hash[:12]}...{anchor_hash[-12:]}" if anchor_hash else "N/A"

    card1, card2, card3 = st.columns(3)
    ecdsa_status = "Hợp lệ" if not any("Chữ ký số" in issue for issue in integrity_result["issues"]) else "Lỗi xác minh"
    card1.metric("ECDSA Signature", ecdsa_status)
    card2.metric("Merkle Root", short_merkle_root)
    card3.metric("Anchor Snapshot", short_anchor_hash)

    st.caption(f"Security ID mới nhất: {short_security_id}")
    st.caption(f"Hash mới nhất: {short_hash}")

    status_map = {"PASSED": "THÀNH CÔNG", "FAILED": "THẤT BẠI"}
    audit_display = audit_df.copy()
    if not audit_display.empty:
        audit_display["status"] = audit_display["status"].map(status_map).fillna(audit_display["status"])

    with st.expander("Xem chi tiết legacy blockchain"):
        st.dataframe(audit_display, width="stretch")
        st.dataframe(anchor_df, width="stretch")

    if st.button("Giả lập sửa ngẫu nhiên 1 giao dịch", disabled=not is_admin):
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
    if not is_admin:
        st.caption("Cần đăng nhập quản trị để giả lập tamper dữ liệu.")

if st.button("Khôi phục dữ liệu từ CSV gốc", disabled=not is_admin):
    try:
        baseline_df = extract_csv("data/transactions.csv")
        baseline_clean_df = transform_data(baseline_df)
        load_to_db(baseline_clean_df)
        st.success("Đã khôi phục dữ liệu từ CSV gốc và cập nhật luồng Fabric.")
        st.rerun()
    except Exception as exc:
        st.error(f"Khôi phục thất bại: {exc}")
if not is_admin:
    st.caption("Cần đăng nhập quản trị để khôi phục dữ liệu từ CSV gốc.")

with tab_excel:
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

            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric("Tổng doanh thu (CSV)", int(csv_ready_df["amount"].sum()))
            metric_b.metric("Tổng chi phí (CSV)", int(csv_ready_df["cost"].sum()))
            metric_c.metric("Tổng lợi nhuận (CSV)", int(csv_ready_df["profit"].sum()))

            csv_chart_data = csv_ready_df.groupby("date")["amount"].mean().reset_index().sort_values("date")
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
