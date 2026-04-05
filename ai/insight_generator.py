from db.database import get_connection
import pandas as pd

def generate_insight():
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM transactions", conn)

    total_revenue = df["amount"].sum()
    total_cost = df["cost"].sum()
    total_profit = df["profit"].sum()

    top_category = (
        df.groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
        .index[0]
    )

    insight = f"""
    📊 Báo cáo tổng hợp tài chính:

    - Tổng doanh thu: {int(total_revenue)} VND
    - Tổng chi phí: {int(total_cost)} VND
    - Tổng lợi nhuận: {int(total_profit)} VND
    - Danh mục hoạt động tốt nhất: {top_category}

    Khuyến nghị:
    - Tập trung đầu tư marketing cho danh mục {top_category}.
    - Theo dõi hiệu quả chi phí để cải thiện biên lợi nhuận.
    """

    return insight