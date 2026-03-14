#!/usr/bin/env node
import {
  buildApprovePlan,
  buildSwapPlanEthInV2,
  contractRegistry,
  getProvider,
  loadLiveContracts,
  networkSummary,
  quoteV2,
  readPairV2,
  readTokenMeta,
} from './supernova_dex_api.js';

async function main() {
  const provider = getProvider(process.env.ETH_MAINNET_RPC_URL);
  const network = await networkSummary(provider);
  if (!network.ok) {
    throw new Error(`wrong network: chainId=${network.chainId}`);
  }

  const [nova, pair, quote, approvePlan, ethInPlan, liveContracts] = await Promise.all([
    readTokenMeta(provider, 'nova'),
    readPairV2(provider, 'weth', 'nova', false),
    quoteV2(provider, 'weth', 'nova', '0.01'),
    buildApprovePlan(provider, 'nova', 'routerv2', '1'),
    buildSwapPlanEthInV2(provider, 'nova', '0.01', '0x000000000000000000000000000000000000dEaD', false, 50, 1200),
    Promise.resolve(loadLiveContracts()),
  ]);

  console.log(JSON.stringify({
    ok: true,
    network,
    coreContracts: contractRegistry(),
    checks: {
      novaSymbol: nova.symbol,
      volatilePair: pair.pair,
      quoteAvailable: quote.quoteAvailable,
      approveTarget: approvePlan.to,
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
