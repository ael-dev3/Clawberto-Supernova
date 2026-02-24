---
name: supernova-pool-intel
description: OpenClaw skill for Supernova protocol intelligence on Ethereum. Enumerate all Supernova pools from on-chain factories, read gauge/voter/bribe/reward state, fetch liquidity and volume from DexScreener, fetch protocol TVL from DefiLlama, compute transparent APR components, and rank pools by APR/volume/safety. Use this when users need best pool discovery, safety-aware routing, or deterministic Supernova contract reads.
---

# Supernova Pool Intel

## Overview

Use this skill when a user asks to analyze Supernova pools, rank opportunities, evaluate vote/reward flows, or compare high-quality vs risky pools.

This skill is deterministic and API-safe:
- On-chain reads use `cast call` only (no state-changing tx).
- HTTP calls are HTTPS-only and host-allowlisted.
- Outputs are machine-readable JSON + CSV.

## Primary Workflow

1. Run the full scan:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py
```

2. Rank differently when needed:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --sort-by volume
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --sort-by safety
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --sort-by votes
```

3. Restrict to actionable pools:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --only-alive --min-liquidity-usd 50000
```

4. Fast scan mode (no bribes):
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --skip-bribes --sort-by safety
```

5. Fast simulation run:
```bash
bash skills/supernova-pool-intel/scripts/run_local_sims.sh
```

## Read-Only Contract Calls

For direct deterministic calls:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_contract_call.py --list-core
python3 skills/supernova-pool-intel/scripts/supernova_contract_call.py --to 0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2 --sig 'length()(uint256)'
```

Guardrail:
- By default, calls are restricted to known Supernova registry addresses.
- `--allow-any-address` is explicit opt-in for off-registry reads.

## Ranking And Math Rails

APR components are explicit and additive:
1. `reward_apr_pct = reward_rate_per_sec * 31536000 * NOVA_price_usd / liquidity_usd * 100`
2. `fee_apr_pct = volume_24h_usd * fee_rate * 365 / liquidity_usd * 100`
3. `bribe_apr_pct = bribe_epoch_usd * 52 / liquidity_usd * 100`
4. `total_apr_pct = reward_apr_pct + fee_apr_pct + bribe_apr_pct`

Fee source:
- CL pools: on-chain `fee()` in 1e-6 units.
- V2 pools: `PairFactory.getFee(pair, stable)` interpreted as basis points.

Safety rules:
- Official ETH/USDC pools are hard-pinned to `10/10`.
- Low-liquidity, suspicious-branding, and mismatched-quality token pools are penalized.
- Output includes `safety_score`, `safety_tier`, and explicit `safety_reasons`.

## Outputs

Default artifacts:
- `supernova_pool_intel_report.json`
- `supernova_pool_intel_report.csv`

Each row includes:
- Pool identity and token pair
- Gauge status (`is_gauged`, `is_gauge_alive`)
- Liquidity, volume, fee rate, vote share
- APR breakdown (`reward_apr_pct`, `fee_apr_pct`, `bribe_apr_pct`, `total_apr_pct`)
- Safety breakdown (`safety_score`, `safety_tier`, `safety_reasons`)
- Bribe token-level detail (`bribe_rewards` in JSON)

## Strict Mode

Use strict mode for autonomous runs:
```bash
python3 skills/supernova-pool-intel/scripts/supernova_pool_scan.py --strict
```

Strict mode fails if:
- No records remain after filters.
- Any APR/safety output is non-finite.
- An official ETH/USDC pool is not scored `10/10`.

Runtime note:
- Full scans can be heavy when reading every bribe token on every gauge.
- Use `--bribe-token-cap` to bound depth and `--skip-bribes` for quick routing views.

## References

If you need deeper context while answering users:
- Contract map and key addresses: `references/contracts.md`
- Safety scoring details: `references/safety_scoring.md`
