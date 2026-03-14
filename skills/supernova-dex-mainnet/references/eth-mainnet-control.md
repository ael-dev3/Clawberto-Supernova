# ETH Mainnet Control

This section belongs to the Supernova skill itself.

## Purpose

Keep ETH mainnet control checks inside Supernova instead of depending on another skill's execution docs.

## Scope

Readiness and control only:
- RPC/network sanity
- signer presence
- signer address
- signer ETH balance
- core contract targets

No broadcasting is performed here.

## Environment

- RPC env: `ETH_MAINNET_RPC_URL`
- signer env: `ETH_MAINNET_EXEC_PRIVATE_KEY`
- optional override env for the chat wrapper: `SNOVA_PK_ENV`

## Commands

```bash
npm run snova -- "snova control"
npm run snova -- "snova signer"
npm run snova -- "snova signer --pk-env ETH_MAINNET_EXEC_PRIVATE_KEY"
```

## Expected usage

1. load signer env in shell
2. run `snova control`
3. verify:
   - chain id is `1`
   - signer is ready
   - signer address is correct
   - ETH balance is non-zero when execution funding is required
4. use read/planning commands only after control is healthy

## Notes

- Keep raw keys out of repo files.
- `snova control` is the Supernova-native status surface.
- Supernova planning commands remain plan/read-only even when signer env is loaded.
