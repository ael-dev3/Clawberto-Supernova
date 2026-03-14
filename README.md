# Supernova ETH Mainnet Live Contract Archive

This repo is the Supernova-specific archive/workbench.
It keeps:
- verified live Supernova mainnet contract artifacts
- the Python `supernova-pool-intel` skill
- a narrowed TypeScript `supernova-dex-mainnet` planning/read layer for Supernova itself

It does **not** own the generic ETH mainnet control surface anymore.
Canonical ETH mainnet readiness/control now lives in the sibling repo:
- `/Users/marko/.openclaw/workspace/Clawberto-eth-mainnet`
- skill: `skills/eth-mainnet-control`

Use that repo for RPC/signer readiness, balances, allowances, and approval planning.
Use this repo once you are doing Supernova-specific inspection or swap planning.

## Source Of Seed Addresses
- Supernova docs: `https://docs.supernova.xyz/technical-documentation/amm/supernova-contract-addresses`

## Validation Method
- Live check: `eth_getCode` via `https://ethereum.publicnode.com`
- Explorer metadata/source/ABI: RouteScan Etherscan-compatible API on `evm/1`
- Proxy implementations were auto-discovered from explorer metadata and EIP-1967 storage slot checks.

## Structure
- `abi/onchain`: ABI files where explorer returned ABI
- `sources/onchain/<address>`: runtime bytecode + verified source files (if available) + explorer entry
- `metadata`: live-only contract list and source index

## Counts
- Seed addresses from docs: 49
- Additional discovered implementations: 3
- Total discovered addresses: 52
- Live on ETH mainnet: 52
- Excluded (no code on ETH mainnet): 0
- ABI files saved: 22
- Contracts with source saved: 23
- Total `.sol` files saved: 292

## OpenClaw Skills

### 1) Supernova Pool Intel

Production pool-intel scanner:
- Skill path: `skills/supernova-pool-intel`
- Main scanner: `skills/supernova-pool-intel/scripts/supernova_pool_scan.py`
- Contract call helper: `skills/supernova-pool-intel/scripts/supernova_contract_call.py`

Quick start:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py
```

Run local simulations/tests:
```bash
bash skills/supernova-pool-intel/scripts/run_local_sims.sh
```

### 2) Supernova DEX Mainnet (TypeScript-first)

Protocol-specific Supernova read/planning layer:
- Skill path: `skills/supernova-dex-mainnet`
- Chat entrypoint: `skills/supernova-dex-mainnet/scripts/supernova_dex_chat.ts`
- API/helpers: `skills/supernova-dex-mainnet/scripts/supernova_dex_api.ts`

Install / validate:
```bash
npm install
npm run check
```

Supernova-specific examples:
```bash
npm run snova -- "snova contracts"
npm run snova -- "snova pair-v2 weth nova --stable false"
npm run snova -- "snova pool-cl weth nova"
npm run snova -- "snova gauge 0xa9eae009FCa124EB19092f55120fE6BA2cd2f1B5"
npm run snova -- "snova quote-v2 weth nova --amount-in 0.1"
npm run snova -- "snova swap-plan-v2 weth nova --amount-in 0.1 --recipient 0x000000000000000000000000000000000000dEaD --stable false --amount-out-min 1"
npm run snova -- "snova swap-plan-eth-in-v2 nova --amount-in-eth 0.05 --recipient 0x000000000000000000000000000000000000dEaD --stable false"
npm run snova -- "snova swap-plan-eth-out-v2 nova --amount-in 1000 --recipient 0x000000000000000000000000000000000000dEaD --stable false --amount-out-min 0.001"
```

## ETH Mainnet Control Boundary

Run generic readiness/control from `/Users/marko/.openclaw/workspace/Clawberto-eth-mainnet`.
Use that repo's README and `skills/eth-mainnet-control` as the canonical command reference.

## Notes
- Uses ETH mainnet RPC from `ETH_MAINNET_RPC_URL` when set.
- Defaults to `https://ethereum.publicnode.com`.
- `quote-v2` quotes against the actual pair address and returns stable/volatile quote slots separately.
- `swap-plan-v2` / `swap-plan-eth-in-v2` / `swap-plan-eth-out-v2` emit calldata plans only. They do not broadcast.
- Swap plans still include `approvalTarget`, but approval planning itself now belongs in `Clawberto-eth-mainnet`.
- `npm run smoke` performs a live ETH mainnet sanity pass for the narrowed Supernova TS layer.
