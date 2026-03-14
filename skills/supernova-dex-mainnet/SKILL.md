---
name: supernova-dex-mainnet
description: TypeScript-first read and planning skill for Ethereum mainnet + Supernova DEX. Use when you need deterministic ETH mainnet contract reads, Supernova V2/CL pool discovery, gauge/vote inspection, LP position inspection, or calldata planning for approvals and direct single-hop RouterV2 swaps without broadcasting.
---

# Supernova DEX Mainnet

Use this skill for **Ethereum mainnet** Supernova interaction.

## Core rules

- Mainnet only: `chainId = 1`
- Read / plan first. Do not broadcast from this skill.
- Deterministic commands only. Avoid ambiguous natural language for swap plans.
- Print full addresses, token ids, pool ids, and calldata targets.
- Keep RPC configurable with `ETH_MAINNET_RPC_URL`; default is `https://ethereum.publicnode.com`
- Signer env defaults to `ETH_MAINNET_EXEC_PRIVATE_KEY`
- Raw private keys stay out of repo files; use Keychain/env only

## What this skill covers

- network sanity checks
- core Supernova contract registry
- ERC20 token metadata reads
- wallet / token balance reads
- allowance reads
- Supernova V2 pair discovery + reserves
- Supernova CL pool discovery + state reads
- gauge / voter / bribe inspection
- NFPM LP position inspection
- approval calldata planning
- direct single-hop RouterV2 swap calldata planning
- native ETH -> token and token -> native ETH calldata planning

## Commands

Use via:

```bash
npm run snova -- "snova network"
```

Supported commands:

- `snova network`
- `snova signer [--pk-env ETH_MAINNET_EXEC_PRIVATE_KEY]`
- `snova contracts [--all]`
- `snova token <token>`
- `snova balance <owner> <asset|eth>`
- `snova allowance <token> <owner> <spender|alias>`
- `snova pair-v2 <tokenA> <tokenB> [--stable]`
- `snova pool-cl <tokenA> <tokenB>`
- `snova gauge <pool>`
- `snova position <tokenId>`
- `snova quote-v2 <tokenIn> <tokenOut> --amount-in <decimal>`
- `snova approve-plan <token> <spender|alias> --amount <decimal>`
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
- `eth` (pseudo-asset for balance reads; use dedicated ETH swap-plan commands for native ETH routing)

## Notes

- `swap-plan-v2` is **plan only**: it returns calldata + target + value, not a broadcast.
- `snova signer` only checks signer readiness/address/balance; it does not send transactions.
- `quote-v2` uses RouterV2 pair-address quote flow and returns stable/volatile quote slots separately.
- When both stable and volatile V2 pairs exist, set `--stable` explicitly for deterministic route selection.
- `swap-plan-v2` can also accept manual `--amount-out-min` when you already have the minimum output from another source.

## References

- `references/interaction-playbook.md`
- `npm run smoke` for a live ETH mainnet sanity pass of the TS interaction layer
