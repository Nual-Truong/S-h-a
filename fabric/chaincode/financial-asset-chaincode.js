'use strict';

const { Contract } = require('fabric-contract-api');

class FinancialAssetContract extends Contract {
  async initLedger(ctx) {
    return JSON.stringify({
      status: 'ok',
      message: 'Ledger is ready. Use createAsset to add financial records.',
    });
  }

  async assetExists(ctx, assetId) {
    const assetBytes = await ctx.stub.getState(assetId);
    return assetBytes && assetBytes.length > 0;
  }

  _parsePayload(payloadJson) {
    if (!payloadJson) {
      return {};
    }

    try {
      return JSON.parse(payloadJson);
    } catch (error) {
      throw new Error(`Invalid payload JSON: ${error.message}`);
    }
  }

  _buildAsset(assetId, payloadJson) {
    const payload = this._parsePayload(payloadJson);
    return {
      assetId,
      payload,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  async createAsset(ctx, assetId, payloadJson) {
    if (!assetId) {
      throw new Error('assetId is required');
    }

    const exists = await this.assetExists(ctx, assetId);
    if (exists) {
      throw new Error(`Asset already exists: ${assetId}`);
    }

    const asset = this._buildAsset(assetId, payloadJson);
    await ctx.stub.putState(assetId, Buffer.from(JSON.stringify(asset)));
    return JSON.stringify(asset);
  }

  async readAsset(ctx, assetId) {
    if (!assetId) {
      throw new Error('assetId is required');
    }

    const assetBytes = await ctx.stub.getState(assetId);
    if (!assetBytes || assetBytes.length === 0) {
      throw new Error(`Asset not found: ${assetId}`);
    }

    return assetBytes.toString();
  }

  async updateAsset(ctx, assetId, payloadJson) {
    if (!assetId) {
      throw new Error('assetId is required');
    }

    const exists = await this.assetExists(ctx, assetId);
    if (!exists) {
      throw new Error(`Asset not found: ${assetId}`);
    }

    const asset = JSON.parse(await this.readAsset(ctx, assetId));
    asset.payload = this._parsePayload(payloadJson);
    asset.updatedAt = new Date().toISOString();

    await ctx.stub.putState(assetId, Buffer.from(JSON.stringify(asset)));
    return JSON.stringify(asset);
  }

  async deleteAsset(ctx, assetId) {
    if (!assetId) {
      throw new Error('assetId is required');
    }

    const exists = await this.assetExists(ctx, assetId);
    if (!exists) {
      throw new Error(`Asset not found: ${assetId}`);
    }

    await ctx.stub.deleteState(assetId);
    return JSON.stringify({ deleted: true, assetId });
  }

  async queryAllAssets(ctx) {
    const startKey = '';
    const endKey = '';
    const iterator = await ctx.stub.getStateByRange(startKey, endKey);
    const results = [];

    while (true) {
      const response = await iterator.next();
      if (response.value && response.value.value.toString()) {
        results.push({
          key: response.value.key,
          record: JSON.parse(response.value.value.toString('utf8')),
        });
      }

      if (response.done) {
        await iterator.close();
        break;
      }
    }

    return JSON.stringify(results);
  }
}

module.exports = FinancialAssetContract;
