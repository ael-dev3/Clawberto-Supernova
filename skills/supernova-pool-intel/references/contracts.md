# Supernova Contract Map (Ethereum Mainnet)

## Core Contracts

- `GaugeManager (proxy)`: `0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2`
- `GaugeManager (implementation)`: `0x120ea99bdc2da6de1b98fbeb84cfaead96a6a9e3`
- `VoterV3`: `0x1c7bf2532dfa34eeea02c3759e0ca8d87b1d8171`
- `VotingEscrow`: `0x4c3e7640b3e3a39a2e5d030a0c1412d80fee1d44`
- `RewardsDistributor`: `0xb3410a30af5033af822b8ea5ad3bd0a19490ea97`
- `NOVA`: `0x00da8466b296e382e5da2bf20962d0cb87200c78`

## Factory Contracts

- `PairFactory (v2)`: `0x5aef44edfc5a7edd30826c724ea12d7be15bdc30`
- `PairFactory CL`: `0x44b7fbd4d87149efa5347c451e74b9fd18e89c55`

## Critical Read Calls

Gauge/pool enumeration:
- `GaugeManager.pairFactory()`
- `GaugeManager.pairFactoryCL()`
- `PairFactory.allPairsLength()`
- `PairFactory.allPairs(i)`
- `PairFactoryCL.allPairsLength()`
- `PairFactoryCL.allPairs(i)`

Gauge status and rewards:
- `GaugeManager.gauges(pool)`
- `GaugeManager.isGaugeAliveForPool(pool)`
- `Gauge.rewardRate()`
- `Gauge.rewardForDuration()`
- `Gauge.totalSupply()` or `Gauge.totalActiveSupply()`

Vote flow:
- `Voter.weights(pool)`
- `Voter.totalWeight()`

Bribe flow:
- `GaugeManager.internal_bribes(gauge)`
- `GaugeManager.external_bribes(gauge)`
- `Bribe.rewardsListLength()`
- `Bribe.bribeTokens(i)`
- `Bribe.tokenRewardsPerEpoch(token, epochStart)`

Locked value and emissions:
- `VotingEscrow.supply()`
- `VotingEscrow.permanentLockBalance()`
- `VotingEscrow.smNFTBalance()`
- `RewardsDistributor.tokens_per_week(epochStart)`
