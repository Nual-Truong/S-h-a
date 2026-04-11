# Fabric-First Workspace

Thư mục này triển khai chế độ Fabric-first cho project. Luồng chính là ETL -> outbox -> Node client -> Fabric chaincode.

## Vị trí các thành phần

- `chaincode/`: chứa smart contract của Fabric.
- `client/`: chứa ứng dụng Node.js để gọi chaincode.
- `network/`: chứa connection profile và cấu hình kết nối mạng Fabric.

## Chạy nhanh (dev)

1. Sinh crypto + channel artifacts:
	- Bash: `fabric/network/scripts/generate-artifacts.sh`
	- PowerShell: `fabric/network/scripts/generate-artifacts.ps1`

2. Khởi động network:
	- Bash: `fabric/network/scripts/network-up.sh`
	- PowerShell: `fabric/network/scripts/network-up.ps1`

3. Chạy ETL ở root project: `python main_etl.py`

4. ETL sẽ export payload vào `fabric/outbox/financial-assets.json` và thử gọi client Node để submit lên chaincode.

5. Tắt network:
	- Bash: `fabric/network/scripts/network-down.sh`
	- PowerShell: `fabric/network/scripts/network-down.ps1`

## File chính

- `chaincode/financial-asset-chaincode.js`: contract xử lý asset.
- `chaincode/index.js`: entrypoint của chaincode.
- `client/invoke-client.js`: client Node.js gửi transaction.
- `network/connection-profile.example.json`: connection profile mẫu.
- `network/docker-compose.yaml`: compose đầy đủ hơn (peer/orderer/ca/couchdb/cli).
- `network/configtx.yaml`: profile để generate genesis block và channel tx.
- `network/crypto-config.yaml`: mẫu tổ chức/peer để generate crypto.
- `network/scripts/*`: script tạo artifacts và bật/tắt network.
