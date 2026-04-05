from etl.extract import extract_csv
from etl.transform import transform_data
from etl.load import load_to_db

df = extract_csv("data/transactions.csv")
df_clean = transform_data(df)
load_to_db(df_clean)

print("ETL completed successfully")