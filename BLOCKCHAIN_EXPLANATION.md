# Hash Chain Bảo Vệ Dữ Liệu - Giải Thích Chi Tiết

## 1️⃣ HASH CHAIN CHỐNG LẠI SỬA DATA NHƯ THẾ NÀO?

### Cơ Chế Liên Kết Hash (Hash Chain)
```
Block 0: [Data₀] → SHA256(data₀) = hash₀
        ↓
Block 1: [Data₁] → SHA256(hash₀ + data₁) = hash₁
        ↓
Block 2: [Data₂] → SHA256(hash₁ + data₂) = hash₂
```

### Nếu Kẻ Tấn Công Sửa Data:
```
Ban đầu:  Block 0              Block 1              Block 2
          data₀ →hash₀  +  data₁ →hash₁  +  data₂ →hash₂

Tấn công: Block 0              Block 1              Block 2
          data₀' →hash₀'  +  data₁ →hash₁  +  data₂ →hash₂
                   ❌ LỖI                        ❌ LỖI
```

**Tại sao không thể sửa?**
- Nếu sửa `data₀` → hash₀ thay đổi → hash₁ không khớp
- Nếu sửa hash₁ để khớp → hash₂ sẽ không khớp
- Phải sửa **TẤT CẢ** các hash sau nó → rất dễ phát hiện

### Bảo Mật Thêm - ECDSA Signature (Chữ Ký Số)
```python
core_payload = f"{block_index}|{data_hash}|{prev_hash}|{security_id}|{merkle_root}"
signature = sign_block_payload(core_payload)  # ECDSA signature
block_hash = SHA256(core_payload + signature)
```

**Kẻ tấn công cần:**
1. ✅ Sửa data
2. ✅ Tính lại tất cả hash theo sau
3. ❌ **Làm lại chữ ký số (CHỈ CÓ KHÓA BÍ MẬT MỚI BIẾT)**

---

## 2️⃣ DATA CORES NẰM Ở ĐÂU?

### Vị Trí Lưu Trữ Tất Cả Blockchain Data:

| Nội Dung | Bảng DB | Vị Trí File | Mô Tả |
|---------|---------|-----------|-------|
| **Dữ liệu gốc** | `transactions` | `data/sfm.db` | Bảng giao dịch gốc (ngân sách, chi phí, lợi nhuận) |
| **Hash Chain** | `transaction_ledger` | `data/sfm.db` | Blockchain ledger (hash, chữ ký, merkle root) |
| **Audit Log** | `ledger_audit_log` | `data/sfm.db` | Lịch sử kiểm tra blockchain (khi nào check, valid?) |
| **Anchor Commit** | `ledger_anchor_log` | `data/sfm.db` | Tức thời snapshot của hash trên thời điểm cụ thể |
| **Metadata** | `ledger_meta` | `data/sfm.db` | Merkle root, key fingerprint, cấu hình |

### Cấu Trúc Bảng `transaction_ledger`:
```sql
CREATE TABLE transaction_ledger (
    block_index INTEGER PRIMARY KEY,     -- Thứ tự khối (0, 1, 2...)
    data_hash TEXT,                       -- SHA256(dữ liệu giao dịch)
    prev_hash TEXT,                       -- Hash của khối trước
    security_id TEXT,                     -- HMAC-SHA256 chống giả mạo
    merkle_root TEXT,                     -- Hash của toàn bộ chuỗi
    signature TEXT,                       -- ECDSA signature
    block_hash TEXT,                      -- SHA256(payload + signature)
    created_at TEXT                       -- Thời gian tạo
)
```

### Cấu Trúc Bảng `transactions` (dữ liệu gốc):
```sql
CREATE TABLE transactions (
    date TEXT,           -- Ngày giao dịch
    category TEXT,       -- Hạng mục (thu nhập, chi phí...)
    amount INTEGER,      -- Số tiền
    cost INTEGER,        -- Chi phí
    profit INTEGER       -- Lợi nhuận
)
```

---

## 3️⃣ KHI DATA MỚI ĐƯỢC THÊM VÀO - ĐƯỢC LƯU Ở ĐÂU?

### Quy Trình Thêm Data Mới:

```
Bước 1: Thêm vào bảng gốc
├─ INSERT INTO transactions (date, category, amount, cost, profit)
└─ Vị trí: data/sfm.db → transactions table

Bước 2: Tính toán hash cho khối mới
├─ payload = JSON({date, category, amount, cost, profit})
├─ data_hash = SHA256(payload)
└─ Liên kết với prev_hash của khối trước

Bước 3: Tính Merkle Root
├─ Tính SHA256 của tất cả data_hash trong chain
├─ Gộp lại theo cây Merkle
└─ merkle_root = root_of_tree

Bước 4: Tạo Security ID (HMAC)
├─ payload_for_hmac = f"{block_index}|{data_hash}|{prev_hash}"
├─ security_id = HMAC-SHA256(SECRET_KEY, payload_for_hmac)
└─ Chỉ có người biết SECRET_KEY mới tạo được

Bước 5: Ký số (ECDSA)
├─ core_payload = f"{block_index}|{data_hash}|{prev_hash}|{security_id}|{merkle_root}"
├─ signature = SIGN(core_payload, PRIVATE_KEY)
└─ Chỉ có PRIVATE_KEY mới ký được

Bước 6: Tính Block Hash
├─ block_hash = SHA256(core_payload + signature)
└─ Đây là hash cuối cùng của khối

Bước 7: Lưu vào ledger
├─ INSERT INTO transaction_ledger (...)
└─ Vị trí: data/sfm.db → transaction_ledger table
```

### Ví Dụ Cụ Thể:
```
Ngày: 2026-04-13, Hạng mục: Chi phí, Số tiền: 5000000, Chi phí: 2000000, Lợi nhuận: 3000000

↓ (được chuỗi hash bảo vệ)

transaction_ledger entry:
{
    block_index: 42,
    data_hash: "a1b2c3d4e5f6...",
    prev_hash: "z9y8x7w6v5u4...",
    security_id: "SID-1a2b3c4d5e6f7g8h9i10jk",
    merkle_root: "f1e2d3c4b5a6...",
    signature: "308d02...",  // ECDSA signature dài
    block_hash: "9f8e7d6c5b4a..."
}
```

---

## 4️⃣ KIỂM TRA INTEGRITY (PHÁT HIỆN SỬA ĐỔNG)

### Hàm Verify Ledger:
```python
def verify_ledger(conn):
    """
    Kiểm tra toàn bộ blockchain xem có bị sửa không
    """
    
    1. Đọc tất cả dữ liệu từ transactions table
    2. Tính lại expected_chain = tất cả hash từ đầu
    3. So sánh với transaction_ledger table
    
    Kiểm tra điều kiện:
    ✓ Số lượng khối có khớp?
    ✓ Mỗi data_hash có khớp?
    ✓ Chuỗi prev_hash có liên tục?
    ✓ Merkle root có khớp?
    ✓ Chữ ký ECDSA có hợp lệ?
    ✓ Security ID có khớp?
    
    Nếu tìm lỗi → Trả về: INVALID + chi tiết lỗi
    Nếu không lỗi → Trả về: VALID
```

### Kết Quả Kiểm Tra (Dashboard hiển thị):
```
ECDSA Signature: Hợp lệ / Lỗi xác minh
Merkle Root: Khớp / Không khớp
Blockchain Status: Valid / Invalid
Latest Hash: a1b2c3d4e5f6...
Blocks: 42
```

---

## 5️⃣ ANCHOR SNAPSHOT (Chứng Thực Thời Gian)

### Tại Sao Cần Anchor?
```
Ngày 1: Tính blockchain → hash₁ = OK
Ngày 30: Kẻ tấn công sửa toàn bộ blockchain
        → Tính lại toàn bộ hash → hash₁' = giống ban đầu
        
❓ Làm sao biết đã bị sửa?
→ Dùng anchor snapshot! Lưu hash₁ vào anchor_log với timestamp
```

### Anchor Log (Chứng Thực):
```sql
CREATE TABLE ledger_anchor_log (
    id INTEGER PRIMARY KEY,
    anchored_at TEXT,           -- Khi nào lock
    latest_hash TEXT,           -- Hash tại thời điểm lock
    merkle_root TEXT,           -- Merkle root tại lúc lock
    anchor_hash TEXT,           -- Hash của anchor entry (phòng sửa anchor)
    note TEXT                   -- Ghi chú (rebuild, manual, auto...)
)
```

---

## 📊 TÓMASIZE: CÁCH BẢO VỆ

```
┌─────────────────────────────────────────────────────┐
│ LUỒNG BẢO VỀ BLOCKCHAIN                             │
├─────────────────────────────────────────────────────┤
│                                                     
│ 1. DATA HASHING (SHA256)                           
│    Nếu sửa 1 byte → hash thay đổi hoàn toàn       
│                                                     
│ 2. HASH CHAIN (Liên kết)                           
│    Khối sau phụ thuộc khối trước                   
│    Sửa 1 khối → phải sửa TẤT CẢ sau                
│                                                     
│ 3. ECDSA SIGNATURE (Chữ ký)                        
│    Chỉ có SECRET_KEY mới ký được                  
│    Chữ ký không khớp → phát hiện                  
│                                                     
│ 4. MERKLE ROOT (Cây hash)                          
│    Hash của toàn bộ chain                          
│    Sửa 1 dữ liệu → merkle root đổi                
│                                                     
│ 5. ANCHOR SNAPSHOT (Khóa thời gian)                
│    Lưu hash tại từng thời điểm                     
│    Sửa sau → không khớp với anchor cũ             
│                                                     
└─────────────────────────────────────────────────────┘
```

---

## 🔐 SECURITY KEYS

### Secret Key (Khóa Bí Mật):
```python
SECRET_ENV_NAME = "BLOCKCHAIN_SECRET_KEY"
DEFAULT_SECRET = "dev-secret-change-me"
# Dùng để tính HMAC security_id
```

### Private Key (ECDSA):
```python
# Sinh từ secret key bằng SECP256k1
signing_key = derive_from_secret(secret)
signature = signing_key.sign(payload)
```

### Public Key:
```python
# Để xác minh chữ ký
verifying_key = signing_key.get_verifying_key()
verified = verifying_key.verify(signature, payload)
```

---

## ⚠️ ĐIỂM YẾU & CÁCH KHẮC PHỤC

| Điểm Yếu | Tấn Công Có Thể | Cách Khắc Phục |
|---------|-----------------|----------------|
| Secret key bị lộ | Tính lại tất cả signature | Thay secret key → auto rebuild |
| DB bị crop toàn bộ | Mất toàn bộ dữ liệu | Sao lưu DB định kỳ |
| Anchor bị sửa | Sửa cả quá khứ | Lưu anchor ngoài database (3rd party) |
| Khóa private bị lộ | Giả mạo chữ ký | Sử dụng HSM hoặc KMS |

---

## 📝 KIỂM TRA BLOCKCHAIN THỰC TẾ

### Chạy kiểm tra:
```bash
cd e:\VLU\Số Hóa\Số Hóa
python blockchain/verify_chain.py
```

### Output ví dụ:
```
Blockchain integrity check: PASSED
Blocks: 42
Latest hash: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
Latest security ID: SID-1a2b3c4d5e6f7g8h9i10jk
Merkle root: f1e2d3c4b5a6x7y8z9a0b1c2d3e4f5g6h7i8j9k0
```

---

## 📁 TÓM LƯỢC VỊ TRÍ FILE

```
e:\VLU\Số Hóa\Số Hóa\
├── data/
│   └── sfm.db                    ← TẤT CẢ BLOCKCHAIN DATA
│       ├── transactions          ← Dữ liệu gốc
│       ├── transaction_ledger    ← Hash chain
│       ├── ledger_audit_log      ← Audit trail
│       ├── ledger_anchor_log     ← Anchor snapshots
│       └── ledger_meta           ← Metadata (merkle root, keys)
│
├── blockchain/
│   ├── ledger.py                 ← Rebuild & verify logic
│   ├── merkle.py                 ← Merkle root calculation
│   ├── security.py               ← ECDSA & HMAC signing
│   └── verify_chain.py           ← Kiểm tra CLI
│
└── main_etl.py                   ← Rebuild ledger khi thêm data
```

---

Generated: 2026-04-13 | Blockchain: LEGACY (Optional)
