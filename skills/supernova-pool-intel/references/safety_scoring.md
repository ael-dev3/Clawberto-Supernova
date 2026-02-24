# Safety Scoring Model

## Goal

Provide deterministic pool risk classification so OpenClaw can separate high-quality pools from low-quality/suspicious pools.

## Hard Rule

- Official ETH/USDC pools are always scored `10.0 / 10.0`.

Official addresses:
- ETH/WETH: `0x0000000000000000000000000000000000000000`, `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`
- USDC: `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`

## Token-Level Signal

Token baseline:
- Official ETH/USDC: `10`
- NOVA: `8`
- Blue-chip quotes (USDT, DAI, WBTC, EURC, XAUT): `9`
- Unknown default: `5`

Penalties:
- Missing symbol: `-1`
- Overlong symbol: `-1`
- Suspicious branding pattern (`SCAM`, `RUG`, `PUMP`, `INU`, etc.): `-3`

## Pool-Level Signal

Base pool score:
- `0.65 * min(token_scores) + 0.35 * max(token_scores)`

Adjustments:
- Liquidity:
  - `>= $1,000,000`: `+1.5`
  - `>= $250,000`: `+0.75`
  - `< $25,000`: `-1.5`
  - `< $5,000`: `-2.5`
- Activity:
  - volume/liquidity `>= 0.5`: `+0.5`
  - volume/liquidity `< 0.01`: `-0.5`
- Age:
  - `< 3 days`: `-1.5`
  - `< 14 days`: `-0.5`
  - `>= 180 days`: `+0.5`
- Quality mismatch (one strong token + one very weak token): `-1.0`

Final clamp:
- `score = min(max(score, 0), 10)`

## Tiers

- `high`: `>= 9`
- `medium`: `>= 7 and < 9`
- `speculative`: `>= 4 and < 7`
- `high-risk`: `< 4`
