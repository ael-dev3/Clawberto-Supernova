#!/usr/bin/env node
import {
  CORE_CONTRACTS,
  buildApprovePlan,
  buildSwapPlanEthInV2,
  buildSwapPlanEthOutV2,
  buildSwapPlanV2,
  contractRegistry,
  getProvider,
  loadLiveContracts,
  networkSummary,
  quoteV2,
  readAllowance,
  readBalance,
  readClPool,
  readGauge,
  readPairV2,
  readPosition,
  readTokenMeta,
  resolveAliasOrAddress,
} from './supernova_dex_api.js';

type ParsedArgs = {
  positionals: string[];
  flags: Map<string, string | true>;
};

function tokenize(argv: string[]): string[] {
  const raw = argv.length === 1 ? argv[0].trim() : argv.join(' ').trim();
  return raw.split(/\s+/).filter(Boolean);
}

function parseArgs(argv: string[]): ParsedArgs {
  const tokens = tokenize(argv);
  if (tokens[0] === 'snova' || tokens[0] === 'supernova' || tokens[0] === '/snova') {
    tokens.shift();
  }
  const positionals: string[] = [];
  const flags = new Map<string, string | true>();
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (!token.startsWith('--')) {
      positionals.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = tokens[i + 1];
    if (!next || next.startsWith('--')) {
      flags.set(key, true);
      continue;
    }
    flags.set(key, next);
    i += 1;
  }
  return { positionals, flags };
}

function getFlag(parsed: ParsedArgs, name: string, fallback?: string): string | undefined {
  const value = parsed.flags.get(name);
  if (typeof value === 'string') return value;
  if (value === true) return 'true';
  return fallback;
}

function getBoolFlag(parsed: ParsedArgs, name: string): boolean | null {
  const value = parsed.flags.get(name);
  if (value === undefined) return null;
  if (value === true) return true;
  const text = String(value).toLowerCase();
  if (['1', 'true', 'yes', 'y'].includes(text)) return true;
  if (['0', 'false', 'no', 'n'].includes(text)) return false;
  throw new Error(`Invalid boolean for --${name}: ${value}`);
}

function requirePositional(parsed: ParsedArgs, index: number, label: string): string {
  const value = parsed.positionals[index];
  if (!value) throw new Error(`Missing ${label}`);
  return value;
}

function print(payload: unknown): never {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  process.exit(0);
}

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  const command = parsed.positionals[0];
  if (!command) {
    throw new Error('Missing command');
  }
  const provider = getProvider(process.env.ETH_MAINNET_RPC_URL);

  switch (command) {
    case 'network': {
      print(await networkSummary(provider));
    }
    case 'contracts': {
      const registry = contractRegistry();
      const all = getBoolFlag(parsed, 'all');
      if (all) {
        print({
          core: registry,
          liveContracts: loadLiveContracts()
        });
      }
      print({ core: registry });
    }
    case 'token': {
      const token = requirePositional(parsed, 1, 'token');
      print(await readTokenMeta(provider, token));
    }
    case 'balance': {
      const owner = requirePositional(parsed, 1, 'owner');
      const asset = requirePositional(parsed, 2, 'asset');
      print(await readBalance(provider, owner, asset));
    }
    case 'allowance': {
      const token = requirePositional(parsed, 1, 'token');
      const owner = requirePositional(parsed, 2, 'owner');
      const spender = requirePositional(parsed, 3, 'spender');
      print(await readAllowance(provider, token, owner, spender));
    }
    case 'pair-v2': {
      const tokenA = requirePositional(parsed, 1, 'tokenA');
      const tokenB = requirePositional(parsed, 2, 'tokenB');
      const stable = getBoolFlag(parsed, 'stable') ?? false;
      print(await readPairV2(provider, tokenA, tokenB, stable));
    }
    case 'pool-cl': {
      const tokenA = requirePositional(parsed, 1, 'tokenA');
      const tokenB = requirePositional(parsed, 2, 'tokenB');
      print(await readClPool(provider, tokenA, tokenB));
    }
    case 'gauge': {
      const pool = requirePositional(parsed, 1, 'pool');
      print(await readGauge(provider, pool));
    }
    case 'position': {
      const tokenId = BigInt(requirePositional(parsed, 1, 'tokenId'));
      print(await readPosition(provider, tokenId));
    }
    case 'quote-v2': {
      const tokenIn = requirePositional(parsed, 1, 'tokenIn');
      const tokenOut = requirePositional(parsed, 2, 'tokenOut');
      const amountIn = getFlag(parsed, 'amount-in');
      if (!amountIn) throw new Error('Missing --amount-in');
      print(await quoteV2(provider, tokenIn, tokenOut, amountIn));
    }
    case 'approve-plan': {
      const token = requirePositional(parsed, 1, 'token');
      const spender = requirePositional(parsed, 2, 'spender');
      const amount = getFlag(parsed, 'amount');
      if (!amount) throw new Error('Missing --amount');
      print(await buildApprovePlan(provider, token, spender, amount));
    }
    case 'swap-plan-v2': {
      const tokenIn = requirePositional(parsed, 1, 'tokenIn');
      const tokenOut = requirePositional(parsed, 2, 'tokenOut');
      const amountIn = getFlag(parsed, 'amount-in');
      const recipient = getFlag(parsed, 'recipient');
      if (!amountIn) throw new Error('Missing --amount-in');
      if (!recipient) throw new Error('Missing --recipient');
      print(await buildSwapPlanV2(
        provider,
        tokenIn,
        tokenOut,
        amountIn,
        recipient,
        getBoolFlag(parsed, 'stable'),
        Number(getFlag(parsed, 'slippage-bps', '50')),
        Number(getFlag(parsed, 'deadline-sec', '1200')),
        getFlag(parsed, 'amount-out-min')
      ));
    }
    case 'swap-plan-eth-in-v2': {
      const tokenOut = requirePositional(parsed, 1, 'tokenOut');
      const amountInEth = getFlag(parsed, 'amount-in-eth');
      const recipient = getFlag(parsed, 'recipient');
      if (!amountInEth) throw new Error('Missing --amount-in-eth');
      if (!recipient) throw new Error('Missing --recipient');
      print(await buildSwapPlanEthInV2(
        provider,
        tokenOut,
        amountInEth,
        recipient,
        getBoolFlag(parsed, 'stable'),
        Number(getFlag(parsed, 'slippage-bps', '50')),
        Number(getFlag(parsed, 'deadline-sec', '1200')),
        getFlag(parsed, 'amount-out-min')
      ));
    }
    case 'swap-plan-eth-out-v2': {
      const tokenIn = requirePositional(parsed, 1, 'tokenIn');
      const amountIn = getFlag(parsed, 'amount-in');
      const recipient = getFlag(parsed, 'recipient');
      if (!amountIn) throw new Error('Missing --amount-in');
      if (!recipient) throw new Error('Missing --recipient');
      print(await buildSwapPlanEthOutV2(
        provider,
        tokenIn,
        amountIn,
        recipient,
        getBoolFlag(parsed, 'stable'),
        Number(getFlag(parsed, 'slippage-bps', '50')),
        Number(getFlag(parsed, 'deadline-sec', '1200')),
        getFlag(parsed, 'amount-out-min')
      ));
    }
    case 'alias': {
      const value = requirePositional(parsed, 1, 'alias');
      print({ value, resolved: resolveAliasOrAddress(value) });
    }
    case 'help': {
      print({
        commands: [
          'snova network',
          'snova contracts [--all]',
          'snova token <token>',
          'snova balance <owner> <asset|eth>',
          'snova allowance <token> <owner> <spender|alias>',
          'snova pair-v2 <tokenA> <tokenB> [--stable]',
          'snova pool-cl <tokenA> <tokenB>',
          'snova gauge <pool>',
          'snova position <tokenId>',
          'snova quote-v2 <tokenIn> <tokenOut> --amount-in <decimal>',
          'snova approve-plan <token> <spender|alias> --amount <decimal>',
          'snova swap-plan-v2 <tokenIn> <tokenOut> --amount-in <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]',
          'snova swap-plan-eth-in-v2 <tokenOut> --amount-in-eth <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]',
          'snova swap-plan-eth-out-v2 <tokenIn> --amount-in <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]'
        ],
        aliases: CORE_CONTRACTS
      });
    }
    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

main().catch((error) => {
  process.stderr.write(`${JSON.stringify({ error: error instanceof Error ? error.message : String(error) }, null, 2)}\n`);
  process.exit(1);
});
