'use strict';

const fs = require('fs');
const path = require('path');
const { Wallets } = require('fabric-network');

function readFirstFile(dirPath) {
  const files = fs.readdirSync(dirPath);
  if (!files.length) {
    throw new Error(`No files found in ${dirPath}`);
  }
  return path.join(dirPath, files[0]);
}

async function main() {
  const walletPath = process.env.FABRIC_WALLET_PATH || path.join(__dirname, 'wallet');
  const identityLabel = process.env.FABRIC_IDENTITY || 'appUser';

  const certPath = process.env.FABRIC_CERT_PATH || path.resolve(
    __dirname,
    '..',
    'network',
    'crypto',
    'peerOrganizations',
    'org1.example.com',
    'users',
    'Admin@org1.example.com',
    'msp',
    'signcerts',
    'Admin@org1.example.com-cert.pem'
  );

  const keyPath = process.env.FABRIC_KEY_PATH || readFirstFile(path.resolve(
    __dirname,
    '..',
    'network',
    'crypto',
    'peerOrganizations',
    'org1.example.com',
    'users',
    'Admin@org1.example.com',
    'msp',
    'keystore'
  ));

  if (!fs.existsSync(certPath)) {
    throw new Error(`Certificate file not found: ${certPath}`);
  }
  if (!fs.existsSync(keyPath)) {
    throw new Error(`Private key file not found: ${keyPath}`);
  }

  const cert = fs.readFileSync(certPath, 'utf8');
  const key = fs.readFileSync(keyPath, 'utf8');

  const wallet = await Wallets.newFileSystemWallet(walletPath);
  const identity = {
    credentials: {
      certificate: cert,
      privateKey: key,
    },
    mspId: process.env.FABRIC_MSP_ID || 'Org1MSP',
    type: 'X.509',
  };

  await wallet.put(identityLabel, identity);
  console.log(`Imported identity '${identityLabel}' to wallet: ${walletPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
