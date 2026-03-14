#!/usr/bin/env node
import {
  ZERO,
  buildSwapPlanEthInV2,
  contractRegistry,
  getProvider,
  loadLiveContracts,
  networkSummary,
  quoteV2,
  readClPool,
  readGauge,
  readPairV2,
} from './supernova_dex_api.js';

async function main() {
  const provider = getProvider(process.env.ETH_MAINNET_RPC_URL);
  const network = await networkSummary(provider);
  if (!network.ok) {
    throw new Error(`wrong network: chainId=${network.chainId}`);
  }

  const pair = await readPairV2(provider, 'weth', 'nova', false);
  if (pair.pair === ZERO) {
    throw new Error('expected live WETH/NOVA V2 pair');
  }

  const [clPool, gauge, quote, ethInPlan, liveContracts] = await Promise.all([
    readClPool(provider, 'weth', 'nova'),
    readGauge(provider, pair.pair),
    quoteV2(provider, 'weth', 'nova', '0.01'),
    buildSwapPlanEthInV2(provider, 'nova', '0.01', '0x000000000000000000000000000000000000dEaD', false, 50, 1200),
    Promise.resolve(loadLiveContracts()),
  ]);

  if (!quote.quoteAvailable) {
    throw new Error('expected live WETH/NOVA quote');
  }
  if (gauge.gauge === ZERO) {
    throw new Error('expected gauge for live WETH/NOVA V2 pair');
  }

  console.log(JSON.stringify({
    ok: true,
    network,
    coreContracts: contractRegistry(),
    checks: {
      volatilePair: pair.pair,
      quoteAvailable: quote.quoteAvailable,
      gauge: gauge.gauge,
      gaugeAlive: gauge.alive,
      clPool: clPool.pool,
      clPoolExists: clPool.exists,
      ethInPlanTarget: ethInPlan.to,
      ethInPlanPair: ethInPlan.pair,
      liveContractCount: liveContracts.length,
    }
  }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }, null, 2));
  process.exit(1);
});
