'use strict';

const fs = require('fs');
const path = require('path');
const { Gateway, Wallets, DefaultEventHandlerStrategies } = require('fabric-network');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function resolveInputPath() {
  const explicitPath = process.env.FABRIC_INPUT_PATH;
  if (explicitPath && fs.existsSync(explicitPath)) {
    return explicitPath;
  }

  return path.resolve(__dirname, '..', 'outbox', 'financial-assets.json');
}

async function loadConnectionProfile() {
  const connectionProfilePath = process.env.FABRIC_CONNECTION_PROFILE || path.resolve(__dirname, '..', 'network', 'connection-profile.example.json');
  return loadJson(connectionProfilePath);
}

async function loadAssets() {
  const inputPath = resolveInputPath();
  if (!fs.existsSync(inputPath)) {
    throw new Error(`Fabric input file not found: ${inputPath}`);
  }

  const payload = loadJson(inputPath);
  const assets = payload.assets || [];
  const startOffset = Number(process.env.FABRIC_START_OFFSET || '0');
  const maxAssets = Number(process.env.FABRIC_MAX_ASSETS || '0');

  const sliced = startOffset > 0 ? assets.slice(startOffset) : assets;
  if (maxAssets > 0) {
    return sliced.slice(0, maxAssets);
  }

  return sliced;
}

function isRetriableError(error) {
  const text = (error && (error.stack || error.message || String(error))) || '';
  return (
    text.includes('MVCC_READ_CONFLICT') ||
    text.includes('Event strategy not satisfied') ||
    text.includes('setListenTimeout') ||
    text.includes('No response received from peers')
  );
}

async function submitWithRetry(contract, fnName, args, maxRetries = 2) {
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      return await contract.submitTransaction(fnName, ...args);
    } catch (error) {
      const isLastAttempt = attempt >= maxRetries;
      if (!isRetriableError(error) || isLastAttempt) {
        throw error;
      }

      const backoffMs = 500 * (attempt + 1);
      await sleep(backoffMs);
    }
  }

  throw new Error(`Failed to submit transaction ${fnName}`);
}

async function main() {
  const ccp = await loadConnectionProfile();
  const walletPath = process.env.FABRIC_WALLET_PATH || path.join(__dirname, 'wallet');
  const wallet = await Wallets.newFileSystemWallet(walletPath);
  const identityLabel = process.env.FABRIC_IDENTITY || 'appUser';

  const existingIdentity = await wallet.get(identityLabel);
  if (!existingIdentity) {
    console.error(`Identity ${identityLabel} not found in wallet: ${walletPath}`);
    console.error('Add an X.509 identity before invoking chaincode.');
    process.exit(1);
  }

  const gateway = new Gateway();
  const channelName = process.env.FABRIC_CHANNEL || 'financialchannel';
  const contractName = process.env.FABRIC_CHAINCODE || 'financial-asset';
  const commitTimeout = Number(process.env.FABRIC_COMMIT_TIMEOUT || '600');
  const assets = await loadAssets();

  try {
    await gateway.connect(ccp, {
      wallet,
      identity: identityLabel,
      discovery: { enabled: true, asLocalhost: true },
      eventHandlerOptions: {
        commitTimeout,
        strategy: DefaultEventHandlerStrategies.MSPID_SCOPE_ANYFORTX,
      },
    });

    const network = await gateway.getNetwork(channelName);
    const contract = network.getContract(contractName);

    const results = [];
    for (let i = 0; i < assets.length; i += 1) {
      const asset = assets[i];
      const assetId = asset.asset_id;
      const payload = asset.payload || {};
      let response;
      try {
        response = await submitWithRetry(contract, 'createAsset', [assetId, JSON.stringify(payload)]);
      } catch (error) {
        // Fallback for reruns when a transaction key already exists.
        if ((error.message || '').includes('Asset already exists')) {
          response = await submitWithRetry(contract, 'updateAsset', [assetId, JSON.stringify(payload)]);
        } else {
          throw error;
        }
      }

      results.push({ assetId, response: response.toString() });

      if ((i + 1) % 50 === 0 || i + 1 === assets.length) {
        console.log(`Progress: ${i + 1}/${assets.length}`);
      }
    }

    const sampleSize = Number(process.env.FABRIC_RESULT_SAMPLE_SIZE || '20');
    const sampleResults = results.slice(0, Math.max(sampleSize, 0));

    console.log(JSON.stringify({
      message: 'Fabric sync completed',
      count: results.length,
      sample_count: sampleResults.length,
      start_offset: Number(process.env.FABRIC_START_OFFSET || '0'),
      max_assets: Number(process.env.FABRIC_MAX_ASSETS || '0'),
      sample_results: sampleResults,
    }, null, 2));
  } finally {
    gateway.disconnect();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
