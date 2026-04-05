import pandas as pd
from pathlib import Path

def extract_csv(path):
    df = pd.read_csv(path)
    return df


def extract_excel(path):
    excel_path = Path(path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file Excel: {excel_path}")
    if excel_path.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError("File đầu vào phải có đuôi .xlsx hoặc .xls")

    return pd.read_excel(excel_path)


def save_csv_from_dataframe(df: pd.DataFrame, excel_path: str, output_dir="data/imports"):
    source = Path(excel_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    output_path = target_dir / f"{source.stem}.csv"
    df.to_csv(output_path, index=False)
    return str(output_path)