# Upstream ETH Mainnet Control

Canonical ETH mainnet control no longer lives in this repo.

Use the sibling repo instead:
- repo: `/Users/marko/.openclaw/workspace/Clawberto-eth-mainnet`
- skill: `skills/eth-mainnet-control`

That repo owns the generic mainnet interface/control surface for:
- RPC sanity
- signer readiness
- ETH / ERC20 balance reads
- allowance reads
- approval planning

## Typical sequence

```bash
cd /Users/marko/.openclaw/workspace/Clawberto-eth-mainnet
npm run eth -- "eth control"
npm run eth -- "eth signer"
npm run eth -- "eth allowance nova <owner> routerv2"
npm run eth -- "eth approve-plan nova routerv2 --amount 1"
```

Then switch back here for Supernova-specific work:

```bash
cd /Users/marko/.openclaw/workspace/Clawberto-Supernova
npm run snova -- "snova quote-v2 weth nova --amount-in 0.1"
npm run snova -- "snova swap-plan-v2 weth nova --amount-in 0.1 --recipient <address> --stable false"
```

## Boundary

This repo may still report Supernova contract targets and emit swap plans that include `approvalTarget`, but it should not be treated as the canonical home for generic ETH mainnet readiness or approval workflows.
