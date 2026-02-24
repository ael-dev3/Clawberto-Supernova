from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "supernova_pool_scan.py"
SPEC = importlib.util.spec_from_file_location("supernova_pool_scan", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load supernova_pool_scan.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class SupernovaPoolScanTests(unittest.TestCase):
    def test_official_eth_usdc_pool_is_hard_pinned_to_10(self) -> None:
        token_eth = mod.TokenMeta(
            address=mod.WETH_ADDRESS.lower(),
            symbol="WETH",
            name="Wrapped Ether",
            decimals=18,
            price_usd=3000.0,
            price_source="",
        )
        token_usdc = mod.TokenMeta(
            address=mod.USDC_ADDRESS.lower(),
            symbol="USDC",
            name="USD Coin",
            decimals=6,
            price_usd=1.0,
            price_source="",
        )
        score = mod.score_pool_safety(token_eth, token_usdc, liquidity_usd=10_000, volume_h24_usd=10, pair_created_at_ms=None)
        self.assertEqual(score["score"], 10.0)
        self.assertEqual(score["tier"], "high")

    def test_suspicious_branding_pushes_safety_down(self) -> None:
        scam = mod.TokenMeta(
            address="0x1111111111111111111111111111111111111111",
            symbol="SCAMINU",
            name="Moon Rug Test",
            decimals=18,
            price_usd=None,
            price_source=None,
        )
        nova = mod.TokenMeta(
            address=mod.DEFAULT_NOVA_TOKEN.lower(),
            symbol="NOVA",
            name="SUPERNOVA",
            decimals=18,
            price_usd=0.1,
            price_source="",
        )
        score = mod.score_pool_safety(scam, nova, liquidity_usd=5000, volume_h24_usd=20, pair_created_at_ms=None)
        self.assertLess(score["score"], 5.0)

    def test_apr_component_formulas(self) -> None:
        reward_apr = mod.compute_reward_apr_percent(1.0, 2.0, 1_000_000.0)
        fee_apr = mod.compute_fee_apr_percent(100_000.0, 0.003, 1_000_000.0)
        bribe_apr = mod.compute_bribe_apr_percent(10_000.0, 1_000_000.0)

        self.assertTrue(math.isclose(reward_apr, 6_307.2, rel_tol=1e-9))
        self.assertTrue(math.isclose(fee_apr, 10.95, rel_tol=1e-9))
        self.assertTrue(math.isclose(bribe_apr, 52.0, rel_tol=1e-9))

    def test_sort_by_apr(self) -> None:
        rows = [
            {"pool_address": "a", "total_apr_pct": 1.0, "safety_score": 10, "liquidity_usd": 100},
            {"pool_address": "b", "total_apr_pct": 4.0, "safety_score": 5, "liquidity_usd": 100},
            {"pool_address": "c", "total_apr_pct": 3.0, "safety_score": 9, "liquidity_usd": 100},
        ]
        out = mod.sort_pool_rows(rows, "apr")
        self.assertEqual([r["pool_address"] for r in out], ["b", "c", "a"])


if __name__ == "__main__":
    unittest.main()
