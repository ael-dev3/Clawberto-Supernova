# Supernova DEX Mainnet Interaction Playbook

## Design borrowed from sibling repos

From Clawberto-Kittenswap:
- deterministic command entrypoints
- explicit state reads before action plans
- full identifiers in outputs
- calldata/target evidence over vague prose

From Clawberto-HyperEVM:
- split read/planning from live execution
- do not sign/broadcast in the read/planning layer
- prefer exact command syntax over ambiguous NL

## Core contract aliases

- `routerv2`: `0xbfae8e87053309fde07ab3ca5f4b5345f8e3058f`
- `swaprouter`: `0x72d63a5b080e1b89cc93f9b9f50cbfa5e291c8ac`
- `pairfactory`: `0x5aef44edfc5a7edd30826c724ea12d7be15bdc30`
- `factorycl`: `0x44b7fbd4d87149efa5347c451e74b9fd18e89c55`
- `gaugemanager`: `0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2`
- `voter`: `0x1c7bf2532dfa34eeea02c3759e0ca8d87b1d8171`
- `nfpm`: `0x00d5bbd0fe275efee371a2b34d0a4b95b0c8aaaa`
- `farmingcenter`: `0x428ea5b4ac84ab687851e6a2688411bdbd6c91af`
- `nova`: `0x00da8466b296e382e5da2bf20962d0cb87200c78`
- `weth`: `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`
- `usdc`: `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`

## High-value reads

### V2
- PairFactory `getPair(tokenA, tokenB, stable)`
- RouterV2 `pairFor(tokenA, tokenB, stable)`
- RouterV2 `getReserves(tokenA, tokenB, stable)`
- RouterV2 `getPoolAmountOut(amountIn, tokenIn, pair)`

### CL
- FactoryCL `poolByPair(tokenA, tokenB)`
- Pool `safelyGetStateOfAMM()`
- Pool `getReserves()`
- Pool `tickSpacing()`

### Gauge / vote
- GaugeManager `gauges(pool)`
- GaugeManager `isGaugeAliveForPool(pool)`
- GaugeManager `fetchInternalBribeFromPool(pool)`
- GaugeManager `fetchExternalBribeFromPool(pool)`
- Voter `weights(pool)`
- Voter `totalWeight()`
- Voter `getEpochPoolWeight(epoch, pool)`

### NFPM
- `positions(tokenId)`
- `tokenFarmedIn(tokenId)`
- `farmingApprovals(tokenId)`

## Planning boundary

This skill can build calldata for:
- `approve(address spender, uint256 amount)`
- `swapExactTokensForTokens(...)` on RouterV2 for direct single-hop routes

If RouterV2 quote helpers revert, pass a manual `--amount-out-min` and keep the skill in planning mode.

This skill should not broadcast.
A future separate execution layer can consume the emitted plan.
