# Financial Data Digitization and Analysis

Du an ETL + Dashboard tai chinh voi huong Fabric-first:
- ETL doc du lieu, transform, luu vao SQLite.
- ETL export outbox cho Hyperledger Fabric.
- Dashboard Streamlit hien thi KPI, forecast, anomaly va trang thai Fabric.

## 1) Yeu cau he thong

- Python 3.13
- Node.js LTS (khuyen nghi 18+)
- Docker Desktop (neu chay Fabric network)
- Windows PowerShell
- FastAPI/Uvicorn duoc cai bang `requirements.txt`

## 2) Clone va setup nhanh

```powershell
git clone <repo-url>
cd <repo-folder>

# Neu bi chan script trong PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Setup 1 lenh
./scripts/setup.ps1
```

## 3) Bien moi truong

Du an co file mau [.env.example](.env.example).

Copy thanh `.env` (hoac set truc tiep trong terminal):

```powershell
Copy-Item .env.example .env
```

Cac bien quan trong:
- `APP_MODE=fabric-first` (mac dinh)
- `FABRIC_AUTO_SYNC=1`
- `FABRIC_HASH_MODE=both`
- `FABRIC_COMMIT_TIMEOUT=900`
- `FABRIC_START_OFFSET=0`
- `FABRIC_MAX_ASSETS=300`
- `DASHBOARD_ADMIN_PASSWORD` (tuy chon)

Luu y: project hien tai tu dong doc file `.env` o thu muc goc neu file nay ton tai. Bien trong terminal van co uu tien cao hon file `.env`.

Neu dat `DASHBOARD_ADMIN_PASSWORD`, cac nut thay doi du lieu, sync Fabric, va tamper se chi mo khi nhap dung mat khau quan tri. Neu de trong, dashboard mac dinh o che do admin.

## 4) Chay nhanh (khong can Fabric)

### Mode local (Python)

```powershell
. ./.venv/Scripts/Activate.ps1
python main_etl.py
python -m streamlit run dashboard/app.py
```

Mo trinh duyet tai http://localhost:8501

Neu cong bi ban:

```powershell
python -m streamlit run dashboard/app.py --server.port 8503
```

### Mode local (Docker)

```powershell
./scripts/docker-dashboard.ps1
```

Mo trinh duyet tai http://localhost:8501

Neu muon chay ETL trong Docker:

```powershell
./scripts/docker-etl.ps1
```

Ghi chu:
- Cach nay chi phuc vu phan local Python/Streamlit.
- Fabric network van chay rieng trong `fabric/network`.

### API rieng

```powershell
./scripts/run-api.ps1
```

Mo tai: http://localhost:8000/docs

API co cac endpoint chinh:
- `GET /health`
- `GET /status`
- `GET /logs`
- `GET /report.xlsx`
- `POST /admin/fabric/sync`
- `POST /admin/checkpoint/clear`

Neu dat `DASHBOARD_ADMIN_PASSWORD`, cac endpoint `POST /admin/*` se can header `X-Admin-Password`.

## 5) Chay day du voi Fabric

### 5.1 Khoi dong network

```powershell
./scripts/fabric-up.ps1
```

### 5.2 Chay ETL va dong bo Fabric

```powershell
. ./.venv/Scripts/Activate.ps1
python main_etl.py
```

### 5.3 Chay dashboard

```powershell
./scripts/run-dashboard.ps1
```

### 5.4 Tat network sau khi test

```powershell
./scripts/fabric-down.ps1
```

### Tach ro 2 che do

- Local: `python main_etl.py` hoac `docker compose up --build dashboard`
- Fabric day du: `./scripts/fabric-up.ps1` + `python main_etl.py`

## 6) Auto-resume theo lo dung de lam gi?

Trong tab Fabric cua dashboard:
- Dung khi du lieu lon hoac dong bo bi do giua chung.
- Chia submit thanh nhieu batch nho.
- Cho phep bat dau lai tu `offset` mong muon.
- Giam kha nang timeout khi submit mot lan qua nhieu giao dich.
- Checkpoint auto-resume duoc luu tai `fabric/outbox/sync-checkpoint.json`.

Goi y:
- Data it (vai dong): sync thuong.
- Data lon / tung fail: dung auto-resume.

## 7) Cau truc thu muc chinh

```text
.
|-- ai/
|-- blockchain/
|-- dashboard/
|-- data/
|-- db/
|-- etl/
|-- fabric/
|   |-- chaincode/
|   |-- client/
|   |-- network/
|   `-- outbox/
|-- forecast/
|-- scripts/
|-- config.py
|-- main_etl.py
`-- requirements.txt
```

## 8) Loi thuong gap

1. Khong activate duoc venv tren PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. ./.venv/Scripts/Activate.ps1
```

2. Streamlit bao khong tim thay file:
- Dam bao dang o thu muc goc repo truoc khi chay lenh.

3. Dashboard dang hien trang thai cu:
- Tat terminal Streamlit cu.
- Chay lai voi cong moi va hard refresh trinh duyet.

## 9) Gop y cho nguoi clone tu GitHub

Sau khi clone, chi can:
1. Chay `./scripts/setup.ps1`
2. Chay `python main_etl.py`
3. Chay `./scripts/run-dashboard.ps1`

Neu can Fabric: chay them `./scripts/fabric-up.ps1` truoc buoc ETL.
