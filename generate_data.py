import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

np.random.seed(42)

start_date = datetime(2023, 1, 1)
end_date = datetime(2024, 12, 31)

dates = pd.date_range(start_date, end_date, freq="D")

# Chon 1 linh vuc duy nhat va danh sach san pham cu the.
DOMAIN = "DienMay"
PRODUCT_CATALOG = [
    {
        "product_name": "MayLanhInverter",
        "product_code": "ML01",
        "brand": "Daikin",
        "base_min": 2_400_000,
        "base_max": 4_900_000,
    },
    {
        "product_name": "TuLanhMini",
        "product_code": "TL02",
        "brand": "Aqua",
        "base_min": 1_800_000,
        "base_max": 3_800_000,
    },
    {
        "product_name": "MayGiatCuaNgang",
        "product_code": "MG03",
        "brand": "LG",
        "base_min": 2_900_000,
        "base_max": 4_950_000,
    },
    {
        "product_name": "NoiChienKhongDau",
        "product_code": "NC04",
        "brand": "Philips",
        "base_min": 700_000,
        "base_max": 2_300_000,
    },
    {
        "product_name": "MayLocKhongKhi",
        "product_code": "LK05",
        "brand": "Sharp",
        "base_min": 1_200_000,
        "base_max": 3_500_000,
    },
]


def build_product_id(product_name: str, product_code: str, brand: str) -> str:
    # Dinh dang: ten_hang_ma-so-hang
    return f"{product_name}_{product_code}-{brand}"

data = []

for date in dates:
    for _ in range(random.randint(2, 5)):  # 2-5 transactions per day

        product = random.choice(PRODUCT_CATALOG)

        # Trend tăng dần theo thời gian
        trend_factor = (date.year - 2023) * 20000 + date.month * 2000

        # Seasonality
        if date.month == 12:
            season_factor = 50000
        elif date.month == 2:
            season_factor = -20000
        else:
            season_factor = 0

        base_amount = random.randint(product["base_min"], product["base_max"])
        amount = base_amount + trend_factor + season_factor

        cost = amount * random.uniform(0.6, 0.85)
        profit = amount - cost

        product_id = build_product_id(
            product["product_name"],
            product["product_code"],
            product["brand"],
        )

        data.append([
            date.strftime("%Y-%m-%d"),
            DOMAIN,
            product["product_name"],
            product["product_code"],
            product["brand"],
            product_id,
            int(amount),
            int(cost),
            int(profit)
        ])

# Thêm 5 giao dịch bất thường
for _ in range(5):
    product = PRODUCT_CATALOG[0]
    product_id = build_product_id(
        product["product_name"],
        product["product_code"],
        product["brand"],
    )
    data.append([
        "2024-11-15",
        DOMAIN,
        product["product_name"],
        product["product_code"],
        product["brand"],
        product_id,
        5000000,
        100000,
        4900000
    ])

df = pd.DataFrame(
    data,
    columns=[
        "date",
        "category",
        "product_name",
        "product_code",
        "brand",
        "product_id",
        "amount",
        "cost",
        "profit",
    ],
)

df.to_csv("data/transactions.csv", index=False)

# Fabric demo assets: giu khop thong tin voi cac cot trong file data.
fabric_assets_df = df.copy()
fabric_assets_df.insert(
    0,
    "asset_id",
    [f"ASSET-{i + 1:06d}" for i in range(len(fabric_assets_df))],
)
fabric_assets_df.to_csv("data/fabric_demo_assets.csv", index=False)

print("Dataset generated successfully!")
print("Fabric demo assets generated: data/fabric_demo_assets.csv")