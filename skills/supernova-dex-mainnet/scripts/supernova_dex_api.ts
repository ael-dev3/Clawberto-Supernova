import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  Contract,
  Interface,
  JsonRpcProvider,
  ZeroAddress,
  formatEther,
  formatUnits,
  getAddress,
  parseUnits,
} from 'ethers';

export const ETH_MAINNET_CHAIN_ID = 1n;
export const DEFAULT_RPC_URL = process.env.ETH_MAINNET_RPC_URL || 'https://ethereum.publicnode.com';
export const ZERO = ZeroAddress;
export const WEEK = 7 * 24 * 60 * 60;

export const CORE_CONTRACTS = {
  routerv2: '0xbfae8e87053309fde07ab3ca5f4b5345f8e3058f',
  swaprouter: '0x72d63a5b080e1b89cc93f9b9f50cbfa5e291c8ac',
  pairfactory: '0x5aef44edfc5a7edd30826c724ea12d7be15bdc30',
  factorycl: '0x44b7fbd4d87149efa5347c451e74b9fd18e89c55',
  gaugemanager: '0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2',
  voter: '0x1c7bf2532dfa34eeea02c3759e0ca8d87b1d8171',
  nfpm: '0x00d5bbd0fe275efee371a2b34d0a4b95b0c8aaaa',
  farmingcenter: '0x428ea5b4ac84ab687851e6a2688411bdbd6c91af',
  quoterv2: '0x8217550d36823b1194b58562dac55d7fe8efb727',
  quoter: '0xf9439cd803dcb11fa574bcc8421207f89b529e41',
  nova: '0x00da8466b296e382e5da2bf20962d0cb87200c78',
  weth: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
  usdc: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
} as const;

export type ContractAlias = keyof typeof CORE_CONTRACTS;

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, '../../..');

const ERC20_ABI = [
  'function symbol() view returns (string)',
  'function name() view returns (string)',
  'function decimals() view returns (uint8)'
];

const ROUTER_V2_ABI = [
  'function pairFor(address,address,bool) view returns (address)',
  'function getReserves(address,address,bool) view returns (uint256,uint256)',
  'function getPoolAmountOut(uint256,address,address) view returns (uint256)',
  'function quoteAddLiquidity(address,address,bool,uint256,uint256) view returns (uint256,uint256,uint256)',
  'function swapExactTokensForTokens(uint256 amountIn,uint256 amountOutMin,(address pair,address from,address to,bool stable,bool concentrated,address receiver)[] routes,address to,uint256 deadline) returns (uint256[] amounts)',
  'function swapExactETHForTokens(uint256 amountOutMin,(address pair,address from,address to,bool stable,bool concentrated,address receiver)[] routes,address to,uint256 deadline) payable returns (uint256[] amounts)',
  'function swapExactTokensForETH(uint256 amountIn,uint256 amountOutMin,(address pair,address from,address to,bool stable,bool concentrated,address receiver)[] routes,address to,uint256 deadline) returns (uint256[] amounts)'
];

const PAIR_FACTORY_ABI = [
  'function getPair(address,address,bool) view returns (address)',
  'function getFee(address,bool) view returns (uint256)',
  'function isPair(address) view returns (bool)',
  'function allPairsLength() view returns (uint256)'
];

const PAIR_INFO_ABI = [
  'function token0() view returns (address)',
  'function token1() view returns (address)',
  'function reserve0() view returns (uint256)',
  'function reserve1() view returns (uint256)',
  'function decimals0() view returns (uint256)',
  'function decimals1() view returns (uint256)'
];

const FACTORY_CL_ABI = [
  'function poolByPair(address,address) view returns (address)',
  'function allPairsLength() view returns (uint256)'
];

const CL_POOL_ABI = [
  'function token0() view returns (address)',
  'function token1() view returns (address)',
  'function tickSpacing() view returns (int24)',
  'function getReserves() view returns (uint128,uint128)',
  'function safelyGetStateOfAMM() view returns (uint160,int24,uint16,uint8,uint128,int24,int24)'
];

const GAUGE_MANAGER_ABI = [
  'function gauges(address) view returns (address)',
  'function isGaugeAliveForPool(address) view returns (bool)',
  'function fetchInternalBribeFromPool(address) view returns (address)',
  'function fetchExternalBribeFromPool(address) view returns (address)',
  'function length() view returns (uint256)',
  'function pools(uint256) view returns (address)'
];

const VOTER_ABI = [
  'function weights(address) view returns (uint256)',
  'function totalWeight() view returns (uint256)',
  'function getEpochTotalWeight(uint256) view returns (uint256)',
  'function getEpochPoolWeight(uint256,address) view returns (uint256)'
];

const GAUGE_ABI = [
  'function rewardRate() view returns (uint256)',
  'function rewardForDuration() view returns (uint256)',
  'function totalSupply() view returns (uint256)',
  'function totalActiveSupply() view returns (uint256)'
];

const NFPM_ABI = [
  'function positions(uint256 tokenId) view returns (uint88 nonce,address operator,address token0,address token1,address deployer,int24 tickLower,int24 tickUpper,uint128 liquidity,uint256 feeGrowthInside0LastX128,uint256 feeGrowthInside1LastX128,uint128 tokensOwed0,uint128 tokensOwed1)',
  'function tokenFarmedIn(uint256 tokenId) view returns (address)',
  'function farmingApprovals(uint256 tokenId) view returns (address)',
  'function ownerOf(uint256 tokenId) view returns (address)'
];

export type TokenMeta = {
  address: string;
  symbol: string;
  name: string;
  decimals: number;
};

export type PairV2Details = {
  tokenA: TokenMeta;
  tokenB: TokenMeta;
  token0: TokenMeta | null;
  token1: TokenMeta | null;
  stable: boolean;
  pair: string;
  routerPair: string;
  feeRaw: string | null;
  reserve0Raw: string | null;
  reserve1Raw: string | null;
  reserve0: string | null;
  reserve1: string | null;
};

function stripBom(text: string): string {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

export function epochStart(tsSec: number): number {
  return tsSec - (tsSec % WEEK);
}

export function nowSec(): number {
  return Math.floor(Date.now() / 1000);
}

export function getProvider(rpcUrl = DEFAULT_RPC_URL): JsonRpcProvider {
  return new JsonRpcProvider(rpcUrl, undefined, { staticNetwork: false });
}

export async function networkSummary(provider: JsonRpcProvider) {
  const [network, blockNumber] = await Promise.all([provider.getNetwork(), provider.getBlockNumber()]);
  return {
    rpcUrl: (provider as unknown as { _getConnection?: () => { url: string } })._getConnection?.().url || DEFAULT_RPC_URL,
    chainId: network.chainId.toString(),
    chainName: network.name,
    blockNumber,
    ok: network.chainId === ETH_MAINNET_CHAIN_ID
  };
}

export function contractRegistry(): Record<string, string> {
  return Object.fromEntries(Object.entries(CORE_CONTRACTS).map(([k, v]) => [k, getAddress(v)]));
}

export function loadLiveContracts(): Array<{ address: string; name: string }> {
  const path = resolve(REPO_ROOT, 'metadata/live_contracts_eth_mainnet.json');
  const raw = stripBom(readFileSync(path, 'utf8'));
  const parsed = JSON.parse(raw) as Array<{ address: string; name?: string }>;
  return parsed.map((item) => ({
    address: getAddress(item.address),
    name: item.name || ''
  }));
}

export function resolveAliasOrAddress(value: string): string {
  const key = value.trim().toLowerCase();
  if (key in CORE_CONTRACTS) {
    return getAddress(CORE_CONTRACTS[key as ContractAlias]);
  }
  return getAddress(value.trim());
}

export async function readTokenMeta(provider: JsonRpcProvider, token: string): Promise<TokenMeta> {
  const addr = resolveAliasOrAddress(token);
  const c = new Contract(addr, ERC20_ABI, provider);
  const [symbol, name, decimals] = await Promise.all([
    c.symbol() as Promise<string>,
    c.name() as Promise<string>,
    c.decimals() as Promise<number>
  ]);
  return { address: addr, symbol, name, decimals: Number(decimals) };
}

export async function readPairV2(provider: JsonRpcProvider, tokenAIn: string, tokenBIn: string, stable: boolean): Promise<PairV2Details> {
  const tokenA = await readTokenMeta(provider, tokenAIn);
  const tokenB = await readTokenMeta(provider, tokenBIn);
  const factory = new Contract(CORE_CONTRACTS.pairfactory, PAIR_FACTORY_ABI, provider);
  const router = new Contract(CORE_CONTRACTS.routerv2, ROUTER_V2_ABI, provider);
  const [pairRaw, routerPairRaw] = await Promise.all([
    factory.getPair(tokenA.address, tokenB.address, stable) as Promise<string>,
    router.pairFor(tokenA.address, tokenB.address, stable) as Promise<string>
  ]);
  const pair = getAddress(pairRaw);
  const routerPair = getAddress(routerPairRaw);
  if (pair === ZERO) {
    return {
      tokenA,
      tokenB,
      token0: null,
      token1: null,
      stable,
      pair,
      routerPair,
      feeRaw: null,
      reserve0Raw: null,
      reserve1Raw: null,
      reserve0: null,
      reserve1: null
    };
  }
  const pairInfo = new Contract(pair, PAIR_INFO_ABI, provider);
  const [feeRaw, reserve0Raw, reserve1Raw, token0Addr, token1Addr] = await Promise.all([
    factory.getFee(pair, stable) as Promise<bigint>,
    pairInfo.reserve0() as Promise<bigint>,
    pairInfo.reserve1() as Promise<bigint>,
    pairInfo.token0() as Promise<string>,
    pairInfo.token1() as Promise<string>
  ]);
  const [token0, token1] = await Promise.all([
    readTokenMeta(provider, token0Addr),
    readTokenMeta(provider, token1Addr)
  ]);
  return {
    tokenA,
    tokenB,
    token0,
    token1,
    stable,
    pair,
    routerPair,
    feeRaw: feeRaw.toString(),
    reserve0Raw: reserve0Raw.toString(),
    reserve1Raw: reserve1Raw.toString(),
    reserve0: formatUnits(reserve0Raw, token0.decimals),
    reserve1: formatUnits(reserve1Raw, token1.decimals)
  };
}

export async function readClPool(provider: JsonRpcProvider, tokenAIn: string, tokenBIn: string) {
  const tokenA = await readTokenMeta(provider, tokenAIn);
  const tokenB = await readTokenMeta(provider, tokenBIn);
  const factory = new Contract(CORE_CONTRACTS.factorycl, FACTORY_CL_ABI, provider);
  const poolRaw = await factory.poolByPair(tokenA.address, tokenB.address) as string;
  const pool = getAddress(poolRaw);
  if (pool === ZERO) {
    return { tokenA, tokenB, pool, exists: false };
  }
  const c = new Contract(pool, CL_POOL_ABI, provider);
  const [token0, token1, tickSpacing, reserves, ammState] = await Promise.all([
    c.token0() as Promise<string>,
    c.token1() as Promise<string>,
    c.tickSpacing() as Promise<number>,
    c.getReserves() as Promise<[bigint, bigint]>,
    c.safelyGetStateOfAMM() as Promise<[bigint, number, number, number, bigint, number, number]>
  ]);
  return {
    tokenA,
    tokenB,
    pool,
    exists: true,
    token0: getAddress(token0),
    token1: getAddress(token1),
    tickSpacing: Number(tickSpacing),
    reserve0Raw: reserves[0].toString(),
    reserve1Raw: reserves[1].toString(),
    amm: {
      sqrtPriceX96: ammState[0].toString(),
      tick: Number(ammState[1]),
      lastFeeRaw: Number(ammState[2]),
      pluginConfig: Number(ammState[3]),
      activeLiquidityRaw: ammState[4].toString(),
      nextTick: Number(ammState[5]),
      previousTick: Number(ammState[6])
    }
  };
}

async function tryReadGaugeField(contract: Contract, field: 'rewardRate' | 'rewardForDuration' | 'totalSupply' | 'totalActiveSupply'): Promise<string | null> {
  try {
    const out = await contract[field]() as bigint;
    return out.toString();
  } catch {
    return null;
  }
}

export async function readGauge(provider: JsonRpcProvider, poolIn: string) {
  const pool = resolveAliasOrAddress(poolIn);
  const gaugeManager = new Contract(CORE_CONTRACTS.gaugemanager, GAUGE_MANAGER_ABI, provider);
  const voter = new Contract(CORE_CONTRACTS.voter, VOTER_ABI, provider);
  const ts = nowSec();
  const epoch = epochStart(ts);
  const [gaugeRaw, alive, internalBribeRaw, externalBribeRaw, totalWeight, epochTotalWeight, weight, epochPoolWeight] = await Promise.all([
    gaugeManager.gauges(pool) as Promise<string>,
    gaugeManager.isGaugeAliveForPool(pool) as Promise<boolean>,
    gaugeManager.fetchInternalBribeFromPool(pool) as Promise<string>,
    gaugeManager.fetchExternalBribeFromPool(pool) as Promise<string>,
    voter.totalWeight() as Promise<bigint>,
    voter.getEpochTotalWeight(BigInt(epoch)) as Promise<bigint>,
    voter.weights(pool) as Promise<bigint>,
    voter.getEpochPoolWeight(BigInt(epoch), pool) as Promise<bigint>
  ]);
  const gauge = getAddress(gaugeRaw);
  if (gauge === ZERO) {
    return {
      pool,
      gauge,
      alive,
      internalBribe: getAddress(internalBribeRaw),
      externalBribe: getAddress(externalBribeRaw),
      currentWeightRaw: weight.toString(),
      currentTotalWeightRaw: totalWeight.toString(),
      epochStart: epoch,
      epochPoolWeightRaw: epochPoolWeight.toString(),
      epochTotalWeightRaw: epochTotalWeight.toString(),
      rewardRateRaw: null,
      rewardForDurationRaw: null,
      totalSupplyRaw: null,
      totalActiveSupplyRaw: null
    };
  }
  const gaugeContract = new Contract(gauge, GAUGE_ABI, provider);
  const [rewardRateRaw, rewardForDurationRaw, totalSupplyRaw, totalActiveSupplyRaw] = await Promise.all([
    tryReadGaugeField(gaugeContract, 'rewardRate'),
    tryReadGaugeField(gaugeContract, 'rewardForDuration'),
    tryReadGaugeField(gaugeContract, 'totalSupply'),
    tryReadGaugeField(gaugeContract, 'totalActiveSupply')
  ]);
  return {
    pool,
    gauge,
    alive,
    internalBribe: getAddress(internalBribeRaw),
    externalBribe: getAddress(externalBribeRaw),
    currentWeightRaw: weight.toString(),
    currentTotalWeightRaw: totalWeight.toString(),
    epochStart: epoch,
    epochPoolWeightRaw: epochPoolWeight.toString(),
    epochTotalWeightRaw: epochTotalWeight.toString(),
    rewardRateRaw,
    rewardForDurationRaw,
    totalSupplyRaw,
    totalActiveSupplyRaw
  };
}

export async function readPosition(provider: JsonRpcProvider, tokenId: bigint) {
  const nfpm = new Contract(CORE_CONTRACTS.nfpm, NFPM_ABI, provider);
  const [position, farmedInRaw, farmingApprovalRaw, ownerRaw] = await Promise.all([
    nfpm.positions(tokenId) as Promise<readonly [bigint, string, string, string, string, number, number, bigint, bigint, bigint, bigint, bigint]>,
    nfpm.tokenFarmedIn(tokenId) as Promise<string>,
    nfpm.farmingApprovals(tokenId) as Promise<string>,
    nfpm.ownerOf(tokenId) as Promise<string>
  ]);
  const token0Meta = await readTokenMeta(provider, position[2]);
  const token1Meta = await readTokenMeta(provider, position[3]);
  return {
    tokenId: tokenId.toString(),
    owner: getAddress(ownerRaw),
    farmedIn: getAddress(farmedInRaw),
    farmingApproval: getAddress(farmingApprovalRaw),
    token0: token0Meta,
    token1: token1Meta,
    deployer: getAddress(position[4]),
    tickLower: Number(position[5]),
    tickUpper: Number(position[6]),
    liquidityRaw: position[7].toString(),
    tokensOwed0Raw: position[10].toString(),
    tokensOwed1Raw: position[11].toString(),
    tokensOwed0: formatUnits(position[10], token0Meta.decimals),
    tokensOwed1: formatUnits(position[11], token1Meta.decimals)
  };
}

async function quoteV2Pair(
  router: Contract,
  amountIn: bigint,
  tokenIn: string,
  pair: string,
  decimalsOut: number
): Promise<{ quoteAvailable: boolean; quoteError: string | null; quotedAmountOutRaw: string | null; quotedAmountOut: string | null }> {
  if (pair === ZERO) {
    return {
      quoteAvailable: false,
      quoteError: 'pair does not exist',
      quotedAmountOutRaw: null,
      quotedAmountOut: null
    };
  }
  try {
    const quotedRaw = await router.getPoolAmountOut(amountIn, tokenIn, pair) as bigint;
    return {
      quoteAvailable: true,
      quoteError: null,
      quotedAmountOutRaw: quotedRaw.toString(),
      quotedAmountOut: formatUnits(quotedRaw, decimalsOut)
    };
  } catch (error) {
    return {
      quoteAvailable: false,
      quoteError: error instanceof Error ? error.message : String(error),
      quotedAmountOutRaw: null,
      quotedAmountOut: null
    };
  }
}

export async function quoteV2(provider: JsonRpcProvider, tokenIn: string, tokenOut: string, amountInDecimal: string) {
  const inMeta = await readTokenMeta(provider, tokenIn);
  const outMeta = await readTokenMeta(provider, tokenOut);
  const router = new Contract(CORE_CONTRACTS.routerv2, ROUTER_V2_ABI, provider);
  const pairFactory = new Contract(CORE_CONTRACTS.pairfactory, PAIR_FACTORY_ABI, provider);
  const amountIn = parseUnits(amountInDecimal, inMeta.decimals);
  const [volatilePairRaw, stablePairRaw] = await Promise.all([
    pairFactory.getPair(inMeta.address, outMeta.address, false) as Promise<string>,
    pairFactory.getPair(inMeta.address, outMeta.address, true) as Promise<string>
  ]);
  const volatilePair = getAddress(volatilePairRaw);
  const stablePair = getAddress(stablePairRaw);
  const [volatileQuote, stableQuote] = await Promise.all([
    quoteV2Pair(router, amountIn, inMeta.address, volatilePair, outMeta.decimals),
    quoteV2Pair(router, amountIn, inMeta.address, stablePair, outMeta.decimals)
  ]);
  const best = [
    { mode: 'volatile', pair: volatilePair, ...volatileQuote },
    { mode: 'stable', pair: stablePair, ...stableQuote }
  ].filter((item) => item.quoteAvailable)
    .sort((a, b) => BigInt(b.quotedAmountOutRaw ?? '0') > BigInt(a.quotedAmountOutRaw ?? '0') ? 1 : -1)[0] ?? null;
  return {
    tokenIn: inMeta,
    tokenOut: outMeta,
    amountInRaw: amountIn.toString(),
    amountIn: amountInDecimal,
    quoteAvailable: best !== null,
    bestMode: best?.mode ?? null,
    bestPair: best?.pair ?? null,
    quotedAmountOutRaw: best?.quotedAmountOutRaw ?? null,
    quotedAmountOut: best?.quotedAmountOut ?? null,
    volatile: {
      pair: volatilePair,
      ...volatileQuote
    },
    stable: {
      pair: stablePair,
      ...stableQuote
    }
  };
}

function chooseStableFlag(stableArg: boolean | null, volatilePair: string, stablePair: string): { stable: boolean; warning: string | null } {
  const hasVolatile = volatilePair !== ZERO;
  const hasStable = stablePair !== ZERO;
  if (stableArg !== null) {
    return { stable: stableArg, warning: hasVolatile && hasStable ? 'both stable and volatile pairs exist; quote source may reflect a different direct pool than the forced route' : null };
  }
  if (hasVolatile && hasStable) {
    throw new Error('Both stable and volatile V2 pairs exist; pass --stable true|false for deterministic route selection');
  }
  if (hasStable) return { stable: true, warning: null };
  return { stable: false, warning: null };
}

async function resolveV2Route(provider: JsonRpcProvider, tokenInAddress: string, tokenOutAddress: string, stableArg: boolean | null) {
  const pairFactory = new Contract(CORE_CONTRACTS.pairfactory, PAIR_FACTORY_ABI, provider);
  const [volatilePairRaw, stablePairRaw] = await Promise.all([
    pairFactory.getPair(tokenInAddress, tokenOutAddress, false) as Promise<string>,
    pairFactory.getPair(tokenInAddress, tokenOutAddress, true) as Promise<string>
  ]);
  const volatilePair = getAddress(volatilePairRaw);
  const stablePair = getAddress(stablePairRaw);
  const chosen = chooseStableFlag(stableArg, volatilePair, stablePair);
  const pair = chosen.stable ? stablePair : volatilePair;
  if (pair === ZERO) {
    throw new Error(`No ${chosen.stable ? 'stable' : 'volatile'} V2 pair exists for the requested token pair`);
  }
  return {
    pair,
    chosen,
    volatilePair,
    stablePair
  };
}

export async function buildSwapPlanV2(
  provider: JsonRpcProvider,
  tokenInArg: string,
  tokenOutArg: string,
  amountInDecimal: string,
  recipientArg: string,
  stableArg: boolean | null,
  slippageBps: number,
  deadlineSec: number,
  amountOutMinDecimal?: string
) {
  const tokenIn = await readTokenMeta(provider, tokenInArg);
  const tokenOut = await readTokenMeta(provider, tokenOutArg);
  const recipient = resolveAliasOrAddress(recipientArg);
  const amountIn = parseUnits(amountInDecimal, tokenIn.decimals);
  const router = new Contract(CORE_CONTRACTS.routerv2, ROUTER_V2_ABI, provider);
  const { pair, chosen } = await resolveV2Route(provider, tokenIn.address, tokenOut.address, stableArg);
  let quotedBestRaw: bigint | null = null;
  let quoteWarning: string | null = chosen.warning;
  let amountOutMin: bigint;
  if (amountOutMinDecimal !== undefined) {
    amountOutMin = parseUnits(amountOutMinDecimal, tokenOut.decimals);
    quoteWarning = quoteWarning ?? 'amountOutMin provided manually; router quote skipped';
  } else {
    try {
      quotedBestRaw = await router.getPoolAmountOut(amountIn, tokenIn.address, pair) as bigint;
      amountOutMin = quotedBestRaw * BigInt(Math.max(0, 10_000 - slippageBps)) / 10_000n;
    } catch (error) {
      throw new Error(`Direct router quote failed for requested pair ${pair}: ${error instanceof Error ? error.message : String(error)}. Retry with --amount-out-min <decimal> to supply the minimum manually.`);
    }
  }
  const deadline = BigInt(nowSec() + deadlineSec);
  const routes = [{
    pair,
    from: tokenIn.address,
    to: tokenOut.address,
    stable: chosen.stable,
    concentrated: false,
    receiver: recipient
  }];
  const iface = new Interface(ROUTER_V2_ABI);
  const data = iface.encodeFunctionData('swapExactTokensForTokens', [amountIn, amountOutMin, routes, recipient, deadline]);
  return {
    action: 'swap-plan-v2',
    to: getAddress(CORE_CONTRACTS.routerv2),
    value: '0',
    data,
    tokenIn,
    tokenOut,
    recipient,
    stable: chosen.stable,
    pair,
    amountInRaw: amountIn.toString(),
    amountIn: amountInDecimal,
    quotedBestAmountOutRaw: quotedBestRaw?.toString() ?? null,
    quotedBestAmountOut: quotedBestRaw !== null ? formatUnits(quotedBestRaw, tokenOut.decimals) : null,
    amountOutMinRaw: amountOutMin.toString(),
    amountOutMin: formatUnits(amountOutMin, tokenOut.decimals),
    slippageBps,
    deadline: deadline.toString(),
    warning: quoteWarning,
    approvalTarget: getAddress(CORE_CONTRACTS.routerv2)
  };
}

export async function buildSwapPlanEthInV2(
  provider: JsonRpcProvider,
  tokenOutArg: string,
  amountInEthDecimal: string,
  recipientArg: string,
  stableArg: boolean | null,
  slippageBps: number,
  deadlineSec: number,
  amountOutMinDecimal?: string
) {
  const tokenOut = await readTokenMeta(provider, tokenOutArg);
  const recipient = resolveAliasOrAddress(recipientArg);
  const amountIn = parseUnits(amountInEthDecimal, 18);
  const router = new Contract(CORE_CONTRACTS.routerv2, ROUTER_V2_ABI, provider);
  const { pair, chosen } = await resolveV2Route(provider, CORE_CONTRACTS.weth, tokenOut.address, stableArg);
  let quotedBestRaw: bigint | null = null;
  let quoteWarning: string | null = chosen.warning;
  let amountOutMin: bigint;
  if (amountOutMinDecimal !== undefined) {
    amountOutMin = parseUnits(amountOutMinDecimal, tokenOut.decimals);
    quoteWarning = quoteWarning ?? 'amountOutMin provided manually; router quote skipped';
  } else {
    try {
      quotedBestRaw = await router.getPoolAmountOut(amountIn, CORE_CONTRACTS.weth, pair) as bigint;
      amountOutMin = quotedBestRaw * BigInt(Math.max(0, 10_000 - slippageBps)) / 10_000n;
    } catch (error) {
      throw new Error(`Direct router quote failed for requested pair ${pair}: ${error instanceof Error ? error.message : String(error)}. Retry with --amount-out-min <decimal> to supply the minimum manually.`);
    }
  }
  const deadline = BigInt(nowSec() + deadlineSec);
  const routes = [{
    pair,
    from: getAddress(CORE_CONTRACTS.weth),
    to: tokenOut.address,
    stable: chosen.stable,
    concentrated: false,
    receiver: recipient
  }];
  const iface = new Interface(ROUTER_V2_ABI);
  const data = iface.encodeFunctionData('swapExactETHForTokens', [amountOutMin, routes, recipient, deadline]);
  return {
    action: 'swap-plan-eth-in-v2',
    to: getAddress(CORE_CONTRACTS.routerv2),
    value: amountIn.toString(),
    data,
    tokenIn: { address: ZERO, symbol: 'ETH', name: 'Ether', decimals: 18 },
    tokenOut,
    recipient,
    stable: chosen.stable,
    pair,
    amountInRaw: amountIn.toString(),
    amountIn: amountInEthDecimal,
    quotedBestAmountOutRaw: quotedBestRaw?.toString() ?? null,
    quotedBestAmountOut: quotedBestRaw !== null ? formatUnits(quotedBestRaw, tokenOut.decimals) : null,
    amountOutMinRaw: amountOutMin.toString(),
    amountOutMin: formatUnits(amountOutMin, tokenOut.decimals),
    slippageBps,
    deadline: deadline.toString(),
    warning: quoteWarning,
    approvalTarget: null
  };
}

export async function buildSwapPlanEthOutV2(
  provider: JsonRpcProvider,
  tokenInArg: string,
  amountInDecimal: string,
  recipientArg: string,
  stableArg: boolean | null,
  slippageBps: number,
  deadlineSec: number,
  amountOutMinDecimal?: string
) {
  const tokenIn = await readTokenMeta(provider, tokenInArg);
  const recipient = resolveAliasOrAddress(recipientArg);
  const amountIn = parseUnits(amountInDecimal, tokenIn.decimals);
  const router = new Contract(CORE_CONTRACTS.routerv2, ROUTER_V2_ABI, provider);
  const { pair, chosen } = await resolveV2Route(provider, tokenIn.address, CORE_CONTRACTS.weth, stableArg);
  let quotedBestRaw: bigint | null = null;
  let quoteWarning: string | null = chosen.warning;
  let amountOutMin: bigint;
  if (amountOutMinDecimal !== undefined) {
    amountOutMin = parseUnits(amountOutMinDecimal, 18);
    quoteWarning = quoteWarning ?? 'amountOutMin provided manually; router quote skipped';
  } else {
    try {
      quotedBestRaw = await router.getPoolAmountOut(amountIn, tokenIn.address, pair) as bigint;
      amountOutMin = quotedBestRaw * BigInt(Math.max(0, 10_000 - slippageBps)) / 10_000n;
    } catch (error) {
      throw new Error(`Direct router quote failed for requested pair ${pair}: ${error instanceof Error ? error.message : String(error)}. Retry with --amount-out-min <decimal> to supply the minimum manually.`);
    }
  }
  const deadline = BigInt(nowSec() + deadlineSec);
  const routes = [{
    pair,
    from: tokenIn.address,
    to: getAddress(CORE_CONTRACTS.weth),
    stable: chosen.stable,
    concentrated: false,
    receiver: recipient
  }];
  const iface = new Interface(ROUTER_V2_ABI);
  const data = iface.encodeFunctionData('swapExactTokensForETH', [amountIn, amountOutMin, routes, recipient, deadline]);
  return {
    action: 'swap-plan-eth-out-v2',
    to: getAddress(CORE_CONTRACTS.routerv2),
    value: '0',
    data,
    tokenIn,
    tokenOut: { address: ZERO, symbol: 'ETH', name: 'Ether', decimals: 18 },
    recipient,
    stable: chosen.stable,
    pair,
    amountInRaw: amountIn.toString(),
    amountIn: amountInDecimal,
    quotedBestAmountOutRaw: quotedBestRaw?.toString() ?? null,
    quotedBestAmountOut: quotedBestRaw !== null ? formatEther(quotedBestRaw) : null,
    amountOutMinRaw: amountOutMin.toString(),
    amountOutMin: formatEther(amountOutMin),
    slippageBps,
    deadline: deadline.toString(),
    warning: quoteWarning,
    approvalTarget: getAddress(CORE_CONTRACTS.routerv2)
  };
}

