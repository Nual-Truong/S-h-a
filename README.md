📊 Financial Data Digitization & Analysis Project
📌 Giới thiệu

Dự án này nhằm mục tiêu số hóa dữ liệu tài chính, xây dựng quy trình ETL, lưu trữ dữ liệu vào cơ sở dữ liệu, thực hiện phân tích – dự báo doanh thu, và trực quan hóa kết quả bằng dashboard.

Dự án phù hợp cho sinh viên CNTT năm 2–3, minh họa cách áp dụng Python vào xử lý dữ liệu thực tế.

🎯 Mục tiêu

Số hóa dữ liệu tài chính từ file CSV

Xây dựng quy trình ETL (Extract – Transform – Load)

Lưu trữ dữ liệu bằng SQLite

Dự báo doanh thu tháng tiếp theo

Trực quan hóa dữ liệu qua Streamlit Dashboard

🛠️ Công nghệ sử dụng

Python 3.13

Pandas – xử lý dữ liệu

SQLite – cơ sở dữ liệu

Statsmodels – dự báo (ARIMA)

Streamlit – dashboard

SHA-256 Hash Chain – blockchain local để xác thực toàn vẹn dữ liệu

Security ID (HMAC-SHA256) – ID bảo mật cho từng block blockchain

ECDSA Signature – chữ ký số cho từng block

Merkle Root – đại diện toàn vẹn cho toàn bộ giao dịch

Anchor Snapshot – neo hash snapshot để theo dõi lịch sử

Beekeeper Studio – xem database (tùy chọn)

📁 Cấu trúc thư mục
E:\VLU\Số Hóa\Số Hóa\
├─ data\
│  ├─ transactions.csv     # Dữ liệu đầu vào
│  ├─ fabric_demo_assets.csv # Asset demo cho Fabric (khớp cột dữ liệu)
│  └─ sfm.db               # Database SQLite
│
├─ db\
│  └─ database.py          # Kết nối database
│
├─ etl\
│  ├─ extract.py           # Đọc dữ liệu CSV
│  ├─ transform.py         # Làm sạch & xử lý dữ liệu
│  └─ load.py              # Lưu dữ liệu vào DB
│
├─ forecast\
│  └─ revenue_forecast.py  # Dự báo doanh thu
│
├─ blockchain\
│  ├─ ledger.py            # Tạo và xác minh blockchain hash-chain
│  └─ verify_chain.py      # Kiểm tra toàn vẹn dữ liệu từ blockchain
│
├─ dashboard\
│  └─ app.py               # Dashboard Streamlit
│
├─ demo_blockchain_flow.py # Demo tự động PASS -> FAIL -> PASS
│
└─ main_etl.py              # Chạy toàn bộ ETL
⚙️ Cài đặt môi trường (khuyến nghị dùng virtual environment)

1) Mở PowerShell và vào thư mục dự án:

```powershell
cd "E:\VLU\Số Hóa\Số Hóa"
```

2) Tạo môi trường ảo (chỉ làm 1 lần):

```powershell
python -m venv .venv
```

Nếu máy có `py launcher`, bạn cũng có thể dùng:

```powershell
py -3.13 -m venv .venv
```

3) Kích hoạt môi trường ảo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell báo chặn script, chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

4) Cài thư viện:

```powershell
python -m pip install -r requirements.py
```

Ghi chú: sqlite3 đã có sẵn trong Python.

5) (Khuyến nghị) Đặt khóa bí mật để tạo Security ID ổn định theo môi trường:

```powershell
$env:BLOCKCHAIN_SECRET_KEY = "your-strong-secret-key"
```

Nếu không đặt biến này, hệ thống sẽ dùng khóa mặc định cho môi trường dev.

▶️ Cách chạy dự án (sau khi đã kích hoạt .venv)

0) (Khuyến nghị) Tạo lại dataset theo lĩnh vực + sản phẩm cụ thể:

```powershell
python generate_data.py
```

Sau khi chạy, dữ liệu có thêm các cột:
- `product_name`
- `product_code`
- `brand`
- `product_id` (định dạng: `ten_hang_ma-so-hang`, ví dụ `MayLanhInverter_ML01-Daikin`)

Đồng thời sinh file `data/fabric_demo_assets.csv` để demo asset Fabric, khớp các cột dữ liệu trong `transactions.csv`.

1) Kiểm tra dữ liệu đầu vào:

```powershell
type data\transactions.csv
```

File không được rỗng.

2) Chạy ETL (CSV -> SQLite + blockchain ledger):

```powershell
python main_etl.py
```

Kết quả mong đợi:

```text
Data loaded successfully
Blockchain ledger rebuilt: ... blocks
ETL completed successfully
```

Mỗi block sẽ có thêm `Security ID` để tăng khả năng xác thực.

3) Chạy dự báo doanh thu:

```powershell
python -m forecast.revenue_forecast
```

4) Chạy dashboard Streamlit:

```powershell
python -m streamlit run dashboard/app.py
```

Mở trình duyệt tại: http://localhost:8501

Nếu cổng 8501 đang bận hoặc phiên cũ còn cache, chạy cổng mới:

```powershell
python -m streamlit run dashboard/app.py --server.port 8503
```

Sau đó mở: http://localhost:8503

5) Kiểm tra toàn vẹn blockchain (tùy chọn):

```powershell
python -m blockchain.verify_chain
```

Kết quả mong đợi:

```text
Blockchain integrity check: PASSED
```

Khi chạy verify, hệ thống kiểm tra thêm độ khớp của Security ID trên từng block.

Ngoài ra verify còn kiểm tra:
- Chữ ký số ECDSA của từng block.
- Merkle root của tập giao dịch.
- Tính hợp lệ của anchor hash snapshot gần nhất.

🔬 Demo blockchain thành công và thất bại

1) Kịch bản THÀNH CÔNG (PASS)

```powershell
python main_etl.py
python -m blockchain.verify_chain
```

Kết quả mong đợi:

```text
Blockchain integrity check: PASSED
```

2) Kịch bản THẤT BẠI (FAIL) để demo phát hiện sửa dữ liệu

```powershell
python -c "from db.database import get_connection; from blockchain.ledger import tamper_random_transaction; conn = get_connection(); tamper_random_transaction(conn, amount_delta=1234); conn.close(); print('Tamper done')"
python -m blockchain.verify_chain
```

Kết quả mong đợi:

```text
Blockchain integrity check: FAILED
... Data hash mismatch ...
```

3) Khôi phục về trạng thái PASS sau demo FAIL

```powershell
python main_etl.py
python -m blockchain.verify_chain
```

Giải thích:
- PASS: Dữ liệu giao dịch và sổ cái hash-chain khớp nhau.
- FAIL: Có thay đổi dữ liệu sau khi đã tạo sổ cái, nên blockchain phát hiện sai lệch.

4) Chạy demo tự động PASS -> FAIL -> PASS

```powershell
python demo_blockchain_flow.py
```

Script sẽ tự:
- Rebuild ETL để về PASS.
- Tamper 1 giao dịch để tạo FAIL.
- Rebuild lại để quay về PASS.

🧯 Lỗi thường gặp

1) `source is not recognized`:
- Bạn đang dùng PowerShell, không dùng `source`.
- Dùng `.\.venv\Scripts\Activate.ps1`.

2) `Invalid value: File does not exist: dashboard\app.py`:
- Bạn đang đứng sai thư mục.
- Cần ở đúng thư mục: `E:\VLU\Số Hóa\Số Hóa`.

3) Chạy `python dashboard/app.py` bị lỗi import:
- Dashboard phải chạy qua Streamlit module:
- `python -m streamlit run dashboard/app.py`

4) Dashboard báo lỗi dù code đã sửa (phiên cũ/cached):
- Dừng tất cả tiến trình Streamlit đang chạy.
- Chạy lại bằng cổng mới: `python -m streamlit run dashboard/app.py --server.port 8503`
- Hard refresh trình duyệt (`Ctrl+F5`).

5) Không muốn activate môi trường ảo:
- Có thể chạy trực tiếp bằng python trong .venv:

```powershell
.\.venv\Scripts\python.exe main_etl.py
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```
📊 Chức năng chính

cd "E:\VLU\Số Hóa\Số Hóa"
E:\Python\Python313\python.exe generate_data.py
E:\Python\Python313\python.exe main_etl.py
E:\Python\Python313\python.exe -m forecast.revenue_forecast
E:\Python\Python313\python.exe -m streamlit run dashboard\app.py

Tổng doanh thu, chi phí, lợi nhuận

Biểu đồ doanh thu theo thời gian

Phân tích dữ liệu theo danh mục

Dự báo doanh thu tháng tiếp theo

Kiểm tra toàn vẹn dữ liệu bằng blockchain hash-chain

Lịch sử xác minh blockchain (audit log) hiển thị trên dashboard

Lịch sử anchor hash snapshot hiển thị trên dashboard

Đánh giá độ chính xác dự báo bằng MAE/MAPE

Chuyển đổi Excel theo đường dẫn sang CSV và phân tích trực tiếp trên dashboard

🆕 Phân tích từ file Excel (theo đường dẫn)

1) Mở dashboard:

```powershell
python -m streamlit run dashboard/app.py
```

2) Tại phần "Phân tích dữ liệu từ file Excel":
- Nhập đường dẫn file Excel `.xlsx` hoặc `.xls`.
- Có thể nhập đường dẫn bất kỳ và bấm "Mở đường dẫn trên máy" để mở trực tiếp bằng Explorer.
- Bấm "Chuyển Excel sang CSV và phân tích".

3) Kết quả:
- Hệ thống tạo file CSV trong thư mục `data/imports/`.
- Có nút mở trực tiếp file CSV vừa tạo và thư mục chứa CSV.
- Hiển thị chỉ số doanh thu/chi phí/lợi nhuận từ CSV.
- Vẽ biểu đồ doanh thu theo ngày và bảng tổng hợp theo danh mục.

✅ Checklist test toàn bộ chức năng

1) ETL + blockchain nâng cao:

```powershell
python main_etl.py
python -m blockchain.verify_chain
```

Kỳ vọng: PASSED và có `Latest hash`, `Latest security ID`, `Merkle root`, `Latest anchor hash`.

2) Demo PASS -> FAIL -> PASS tự động:

```powershell
python demo_blockchain_flow.py
```

Kỳ vọng:
- STEP 1: PASSED
- STEP 2: FAILED
- STEP 3: PASSED

3) Dashboard:

```powershell
python -m streamlit run dashboard/app.py --server.port 8503
```

Kỳ vọng trên UI:
- Khối Blockchain hiển thị trạng thái hợp lệ.
- Có lịch sử audit log.
- Có lịch sử anchor hash snapshot.
- Có MAE/MAPE.
- Có khu vực Excel -> CSV -> phân tích.

4) Test tamper trên UI:
- Bấm "Giả lập sửa ngẫu nhiên 1 giao dịch".
- Refresh trang.
- Kỳ vọng verify chuyển sang FAILED.
- Chạy lại `python main_etl.py`, refresh lại.
- Kỳ vọng quay về PASSED.

🧠 Ý nghĩa học tập

Dự án giúp sinh viên:

Hiểu quy trình ETL thực tế

Làm việc với database

Áp dụng phân tích & dự báo dữ liệu

Xây dựng dashboard trực quan

Làm quen với tư duy hệ thống dữ liệu

🚀 Hướng phát triển

Thêm nhiều dữ liệu (1000+ dòng)

Xuất báo cáo Excel / PDF

Phân quyền người dùng

Docker hóa project

Kết nối DB doanh nghiệp (PostgreSQL / SQL Server)

👨‍🎓 Đối tượng phù hợp

Sinh viên Công nghệ Thông tin

Môn học: Số hóa dữ liệu, Phân tích dữ liệu, Python nâng cao

Đồ án nhỏ – trung bình (small–medium project)
