# Supernova ETH Mainnet Live Contract Archive

This folder contains only contracts verified as live on Ethereum mainnet (`chainId 1`).

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
- Total .sol files saved: 292
