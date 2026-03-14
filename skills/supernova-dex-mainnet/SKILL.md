---
name: supernova-dex-mainnet
description: TypeScript-first Supernova DEX skill for Ethereum mainnet. Use after eth-mainnet-control when you need deterministic Supernova V2/CL reads, gauge/vote inspection, NFPM position inspection, or RouterV2 swap planning without broadcasting.
---

# Supernova DEX Mainnet

Use this skill for **Supernova-specific** Ethereum mainnet work.

Generic ETH mainnet control is upstream now:
- repo: `/Users/marko/.openclaw/workspace/Clawberto-eth-mainnet`
- skill: `skills/eth-mainnet-control`

Use that repo first for:
- RPC sanity / chain checks
- signer readiness
- ETH / ERC20 balance reads
- allowance reads
- approval planning

## Core rules

- Mainnet only: `chainId = 1`
- Read / plan first. Do not broadcast from this skill.
- Do not recreate a generic ETH mainnet control layer here.
- Deterministic commands only. Avoid ambiguous natural language for swap plans.
- Print full addresses, token ids, pool ids, and calldata targets.
- Keep RPC configurable with `ETH_MAINNET_RPC_URL`; default is `https://ethereum.publicnode.com`

## What this skill covers

- core Supernova contract registry
- Supernova V2 pair discovery + reserves
- Supernova CL pool discovery + state reads
- gauge / voter / bribe inspection
- NFPM LP position inspection
- direct single-hop RouterV2 swap calldata planning
- native ETH -> token and token -> native ETH swap planning

## Mainnet prerequisite

Complete generic ETH mainnet readiness in `/Users/marko/.openclaw/workspace/Clawberto-eth-mainnet` first.
Use that repo's README and `skills/eth-mainnet-control` as the canonical command reference.

## Commands

Use via:

```bash
npm run snova -- "snova contracts"
```

Supported commands:

- `snova contracts [--all]`
- `snova pair-v2 <tokenA> <tokenB> [--stable]`
- `snova pool-cl <tokenA> <tokenB>`
- `snova gauge <pool>`
- `snova position <tokenId>`
- `snova quote-v2 <tokenIn> <tokenOut> --amount-in <decimal>`
- `snova swap-plan-v2 <tokenIn> <tokenOut> --amount-in <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]`
- `snova swap-plan-eth-in-v2 <tokenOut> --amount-in-eth <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]`
- `snova swap-plan-eth-out-v2 <tokenIn> --amount-in <decimal> --recipient <address> [--stable] [--slippage-bps 50] [--deadline-sec 1200] [--amount-out-min <decimal>]`

## Useful aliases

Contracts:
- `routerv2`
- `swaprouter`
- `pairfactory`
- `factorycl`
- `gaugemanager`
- `voter`
- `nfpm`
- `farmingcenter`
- `quoter`
- `quoterv2`

Tokens:
- `weth`
- `usdc`
- `nova`

## Notes

- `swap-plan-v2` / `swap-plan-eth-in-v2` / `swap-plan-eth-out-v2` are **plan only**: they return calldata + target + value, not a broadcast.
- `quote-v2` uses RouterV2 pair-address quote flow and returns stable/volatile quote slots separately.
- When both stable and volatile V2 pairs exist, set `--stable` explicitly for deterministic route selection.
- Swap plans still include `approvalTarget`, but approval plan generation belongs in `eth-mainnet-control`.
- `npm run smoke` is the live sanity pass for this narrowed Supernova layer.

## References

- `references/interaction-playbook.md`
