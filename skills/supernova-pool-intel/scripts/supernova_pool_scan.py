#!/usr/bin/env python3
"""
Supernova pool intelligence scanner for OpenClaw.

What it does:
- Enumerates all Supernova pools from on-chain factories.
- Pulls gauge/vote/bribe state on-chain.
- Pulls market/liquidity/volume from DexScreener.
- Pulls protocol TVL from DefiLlama.
- Computes transparent APR components:
  - reward APR (gauge emissions)
  - fee APR (24h volume * fee rate annualized)
  - bribe APR (epoch bribes annualized)
- Scores pool safety with explicit reasons and hard-pins official ETH/USDC pools to 10/10.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SECONDS_PER_YEAR = 365 * 24 * 60 * 60
SECONDS_PER_WEEK = 7 * 24 * 60 * 60
DEFAULT_TIMEOUT_SEC = 30
MAX_HTTP_BYTES = 12 * 1024 * 1024
USER_AGENT = "OpenClaw-Supernova-Pool-Intel/1.0"

DEFAULT_RPC_URL = "https://ethereum.publicnode.com"
DEFAULT_GAUGE_MANAGER = "0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2"
DEFAULT_VOTER = "0x1c7bf2532dfa34eeea02c3759e0ca8d87b1d8171"
DEFAULT_VOTING_ESCROW = "0x4c3e7640b3e3a39a2e5d030a0c1412d80fee1d44"
DEFAULT_REWARDS_DISTRIBUTOR = "0xb3410a30af5033af822b8ea5ad3bd0a19490ea97"
DEFAULT_NOVA_TOKEN = "0x00Da8466B296E382E5Da2Bf20962D0cB87200c78"

DEX_PAIR_ENDPOINT = "https://api.dexscreener.com/latest/dex/pairs/ethereum/{pair}"
DEX_TOKEN_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/{token}"
DEFILLAMA_PROTOCOL_ENDPOINT = "https://api.llama.fi/protocol/supernova"

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

ALLOWED_HTTP_HOSTS = {
    "api.dexscreener.com",
    "api.llama.fi",
}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
WBTC_ADDRESS = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
EURC_ADDRESS = "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c"
XAUT_ADDRESS = "0x68749665FF8D2d112Fa859AA293F07A622782F38"

OFFICIAL_ETH_ADDRESSES = {
    ZERO_ADDRESS.lower(),
    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    WETH_ADDRESS.lower(),
}
OFFICIAL_USDC_ADDRESSES = {USDC_ADDRESS.lower()}
BLUE_CHIP_TOKEN_ADDRESSES = {
    USDT_ADDRESS.lower(),
    DAI_ADDRESS.lower(),
    WBTC_ADDRESS.lower(),
    EURC_ADDRESS.lower(),
    XAUT_ADDRESS.lower(),
}

KNOWN_TOKEN_DECIMALS = {
    DEFAULT_NOVA_TOKEN.lower(): 18,
    WETH_ADDRESS.lower(): 18,
    USDC_ADDRESS.lower(): 6,
    USDT_ADDRESS.lower(): 6,
    DAI_ADDRESS.lower(): 18,
    WBTC_ADDRESS.lower(): 8,
    EURC_ADDRESS.lower(): 6,
    XAUT_ADDRESS.lower(): 6,
}

SUSPICIOUS_TEXT_RE = re.compile(
    r"(?:SCAM|RUG|PUMP|MOON|INU|ELON|TEST|FAKE|HONEY)",
    re.IGNORECASE,
)


@dataclass
class TokenMeta:
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: Optional[float]
    price_source: Optional[str]


@dataclass
class PairMarket:
    dex_id: Optional[str]
    pair_url: Optional[str]
    liquidity_usd: float
    volume_h24_usd: float
    txns_h24: int
    pair_created_at_ms: Optional[int]
    base_token_address: str
    base_token_symbol: str
    base_token_name: str
    quote_token_address: str
    quote_token_symbol: str
    quote_token_name: str


def now_iso_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def epoch_start(timestamp: int) -> int:
    return timestamp - (timestamp % SECONDS_PER_WEEK)


def normalize_address(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith("0x"):
        return ""
    if len(text) != 42:
        return ""
    if not ADDRESS_RE.match(text):
        return ""
    return text.lower()


def is_zero_address(value: str) -> bool:
    return normalize_address(value) == ZERO_ADDRESS.lower()


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def make_https_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only https URLs are allowed, got: {url}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HTTP_HOSTS:
        raise ValueError(f"Blocked host '{host}' for URL: {url}")
    return url


def http_get_json(url: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> Any:
    safe_url = make_https_url(url)
    req = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        total = 0
        chunks: List[bytes] = []
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_HTTP_BYTES:
                raise ValueError(f"HTTP response exceeded {MAX_HTTP_BYTES} bytes for {safe_url}")
            chunks.append(chunk)
    data = b"".join(chunks)
    return json.loads(data.decode("utf-8"))


def parse_cast_uint(raw: str) -> int:
    line = (raw or "").strip().splitlines()[0].strip()
    token = line.split()[0]
    if token.startswith("0x"):
        return int(token, 16)
    return int(token)


def parse_cast_bool(raw: str) -> bool:
    line = (raw or "").strip().splitlines()[0].strip().lower()
    if line in {"true", "1"}:
        return True
    if line in {"false", "0"}:
        return False
    raise ValueError(f"Unexpected bool output: {raw}")


def parse_cast_address(raw: str) -> str:
    text = (raw or "").strip()
    for line in text.splitlines():
        token = line.strip().split()[0]
        addr = normalize_address(token)
        if addr:
            return addr
    return ""


def decode_bytes32_text(value: str) -> str:
    token = value.strip().split()[0]
    if not token.startswith("0x") or len(token) != 66:
        return ""
    try:
        b = bytes.fromhex(token[2:])
    except ValueError:
        return ""
    return b.rstrip(b"\x00").decode("utf-8", errors="ignore").strip()


def sanitize_text(value: str) -> str:
    return str(value or "").strip().replace("\n", " ")


class CastClient:
    def __init__(self, rpc_url: str, timeout_sec: int = 20):
        parsed = urllib.parse.urlparse(rpc_url)
        if parsed.scheme != "https":
            raise ValueError(f"RPC URL must be https for safety, got: {rpc_url}")
        self.rpc_url = rpc_url
        self.timeout_sec = timeout_sec
        self._cache: Dict[Tuple[str, str, Tuple[str, ...]], str] = {}
        self._lock = threading.Lock()

    def call(
        self,
        to: str,
        signature: str,
        *args: Any,
        use_cache: bool = True,
        allow_fail: bool = False,
    ) -> Optional[str]:
        to_addr = normalize_address(to)
        if not to_addr:
            if allow_fail:
                return None
            raise ValueError(f"Invalid address: {to}")
        key = (to_addr, signature, tuple(str(x) for x in args))
        if use_cache:
            with self._lock:
                cached = self._cache.get(key)
            if cached is not None:
                return cached

        cmd = [
            "cast",
            "call",
            "--rpc-url",
            self.rpc_url,
            to_addr,
            signature,
            *[str(x) for x in args],
        ]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_sec,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            if allow_fail:
                return None
            raise RuntimeError(f"Failed cast call: {' '.join(cmd)} ({exc})") from exc

        if proc.returncode != 0:
            if allow_fail:
                return None
            err = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Cast call failed ({signature} @ {to_addr}): {err}")

        out = proc.stdout.strip()
        if use_cache:
            with self._lock:
                self._cache[key] = out
        return out


def ensure_cast() -> None:
    try:
        proc = subprocess.run(
            ["cast", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("cast is not installed. Install Foundry first: https://book.getfoundry.sh/getting-started/installation") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"cast is not available: {proc.stderr.strip()}")


def fetch_protocol_tvl_usd() -> Tuple[Optional[float], Optional[float], Optional[str]]:
    try:
        payload = http_get_json(DEFILLAMA_PROTOCOL_ENDPOINT)
    except Exception:
        return None, None, None

    chain_tvl = None
    try:
        chain_tvl = to_float((payload.get("currentChainTvls") or {}).get("Ethereum"), default=0.0)
    except Exception:
        chain_tvl = None

    latest_tvl = None
    latest_tvl_ts = None
    tvl_points = payload.get("tvl") or []
    if isinstance(tvl_points, list) and tvl_points:
        point = tvl_points[-1]
        latest_tvl = to_float(point.get("totalLiquidityUSD"), default=0.0)
        ts = point.get("date")
        try:
            latest_tvl_ts = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc).isoformat()
        except Exception:
            latest_tvl_ts = None

    tvl = chain_tvl if chain_tvl is not None and chain_tvl > 0 else latest_tvl
    return tvl, latest_tvl, latest_tvl_ts


def fetch_pair_market(pair_address: str) -> Optional[PairMarket]:
    url = DEX_PAIR_ENDPOINT.format(pair=pair_address)
    try:
        payload = http_get_json(url)
    except Exception:
        return None

    rows = payload.get("pairs") or []
    if not isinstance(rows, list) or not rows:
        return None

    addr_norm = normalize_address(pair_address)
    selected = None
    for row in rows:
        row_chain = str(row.get("chainId") or "").lower()
        row_addr = normalize_address(row.get("pairAddress"))
        if row_chain == "ethereum" and row_addr == addr_norm:
            selected = row
            break
    if selected is None:
        selected = rows[0]

    txns = selected.get("txns") or {}
    txns_h24 = txns.get("h24") or {}

    base = selected.get("baseToken") or {}
    quote = selected.get("quoteToken") or {}

    return PairMarket(
        dex_id=sanitize_text(selected.get("dexId") or "") or None,
        pair_url=sanitize_text(selected.get("url") or "") or None,
        liquidity_usd=to_float((selected.get("liquidity") or {}).get("usd"), default=0.0),
        volume_h24_usd=to_float((selected.get("volume") or {}).get("h24"), default=0.0),
        txns_h24=int(to_float(txns_h24.get("buys"), default=0.0) + to_float(txns_h24.get("sells"), default=0.0)),
        pair_created_at_ms=int(to_float(selected.get("pairCreatedAt"), default=0.0)) or None,
        base_token_address=normalize_address(base.get("address")),
        base_token_symbol=sanitize_text(base.get("symbol") or ""),
        base_token_name=sanitize_text(base.get("name") or ""),
        quote_token_address=normalize_address(quote.get("address")),
        quote_token_symbol=sanitize_text(quote.get("symbol") or ""),
        quote_token_name=sanitize_text(quote.get("name") or ""),
    )


def fetch_token_spot_price_usd(token_address: str) -> Tuple[Optional[float], Optional[str]]:
    addr = normalize_address(token_address)
    if not addr:
        return None, None

    url = DEX_TOKEN_ENDPOINT.format(token=addr)
    try:
        payload = http_get_json(url)
    except Exception:
        return None, None

    rows = payload.get("pairs") or []
    if not isinstance(rows, list) or not rows:
        return None, None

    best = None
    best_liq = -1.0
    for row in rows:
        if str(row.get("chainId") or "").lower() != "ethereum":
            continue
        price = to_float(row.get("priceUsd"), default=0.0)
        if price <= 0:
            continue
        liq = to_float((row.get("liquidity") or {}).get("usd"), default=0.0)
        if liq > best_liq:
            best_liq = liq
            best = row

    if not best:
        return None, None

    return to_float(best.get("priceUsd"), default=0.0), sanitize_text(best.get("url") or "") or None


def read_erc20_text(cast: CastClient, token: str, method_name: str) -> str:
    out = cast.call(token, f"{method_name}()(string)", allow_fail=True)
    if out:
        line = out.strip().splitlines()[0].strip()
        if line.startswith('"') and line.endswith('"') and len(line) >= 2:
            line = line[1:-1]
        line = sanitize_text(line)
        if line:
            return line

    out_bytes = cast.call(token, f"{method_name}()(bytes32)", allow_fail=True)
    if out_bytes:
        decoded = decode_bytes32_text(out_bytes)
        if decoded:
            return decoded
    return ""


def read_token_meta(
    cast: CastClient,
    token_address: str,
    token_price_cache: Dict[str, Tuple[Optional[float], Optional[str]]],
    token_meta_cache: Dict[str, TokenMeta],
    cache_lock: threading.Lock,
    fallback_symbol: str = "",
    fallback_name: str = "",
) -> TokenMeta:
    addr = normalize_address(token_address)
    if not addr:
        return TokenMeta(
            address="",
            symbol=fallback_symbol or "UNKNOWN",
            name=fallback_name or "Unknown Token",
            decimals=18,
            price_usd=None,
            price_source=None,
        )

    with cache_lock:
        cached = token_meta_cache.get(addr)
    if cached is not None:
        return cached

    symbol = sanitize_text(fallback_symbol or "")
    if not symbol:
        symbol = read_erc20_text(cast, addr, "symbol") or "UNKNOWN"

    name = sanitize_text(fallback_name or "")
    if not name:
        name = read_erc20_text(cast, addr, "name") or symbol

    decimals = KNOWN_TOKEN_DECIMALS.get(addr, 18)
    if addr not in KNOWN_TOKEN_DECIMALS:
        dec_raw = cast.call(addr, "decimals()(uint8)", allow_fail=True)
        if dec_raw:
            try:
                decimals = int(clamp(parse_cast_uint(dec_raw), 0, 255))
            except Exception:
                decimals = 18

    with cache_lock:
        price_info = token_price_cache.get(addr)
    if price_info is None:
        price_info = fetch_token_spot_price_usd(addr)
        with cache_lock:
            token_price_cache[addr] = price_info

    meta = TokenMeta(
        address=addr,
        symbol=symbol,
        name=name,
        decimals=decimals,
        price_usd=price_info[0],
        price_source=price_info[1],
    )
    with cache_lock:
        token_meta_cache[addr] = meta
    return meta


def is_official_eth(addr: str) -> bool:
    return normalize_address(addr) in OFFICIAL_ETH_ADDRESSES


def is_official_usdc(addr: str) -> bool:
    return normalize_address(addr) in OFFICIAL_USDC_ADDRESSES


def score_token_safety(address: str, symbol: str, name: str) -> Tuple[float, List[str]]:
    addr = normalize_address(address)
    sym = (symbol or "").strip().upper()
    nm = (name or "").strip()
    reasons: List[str] = []

    if is_official_eth(addr):
        return 10.0, ["official_eth_token"]
    if is_official_usdc(addr):
        return 10.0, ["official_usdc_token"]

    score = 5.0

    if addr == normalize_address(DEFAULT_NOVA_TOKEN):
        score = 8.0
        reasons.append("supernova_native_token")
    elif addr in BLUE_CHIP_TOKEN_ADDRESSES:
        score = 9.0
        reasons.append("bluechip_quote_token")

    if not sym or sym == "UNKNOWN":
        score -= 1.0
        reasons.append("missing_symbol")
    if len(sym) > 12:
        score -= 1.0
        reasons.append("overlong_symbol")

    if SUSPICIOUS_TEXT_RE.search(sym) or SUSPICIOUS_TEXT_RE.search(nm):
        score -= 3.0
        reasons.append("suspicious_branding_pattern")

    if not addr:
        score -= 2.0
        reasons.append("missing_token_address")

    return clamp(score, 0.0, 10.0), reasons


def score_pool_safety(
    token0: TokenMeta,
    token1: TokenMeta,
    liquidity_usd: float,
    volume_h24_usd: float,
    pair_created_at_ms: Optional[int],
) -> Dict[str, Any]:
    t0_is_eth = is_official_eth(token0.address)
    t1_is_eth = is_official_eth(token1.address)
    t0_is_usdc = is_official_usdc(token0.address)
    t1_is_usdc = is_official_usdc(token1.address)

    if (t0_is_eth and t1_is_usdc) or (t1_is_eth and t0_is_usdc):
        return {
            "score": 10.0,
            "tier": "high",
            "reasons": ["official_eth_usdc_pool_hard_pinned"],
        }

    t0_score, t0_reasons = score_token_safety(token0.address, token0.symbol, token0.name)
    t1_score, t1_reasons = score_token_safety(token1.address, token1.symbol, token1.name)

    score = (min(t0_score, t1_score) * 0.65) + (max(t0_score, t1_score) * 0.35)
    reasons = [*t0_reasons, *t1_reasons]

    if liquidity_usd >= 1_000_000:
        score += 1.5
        reasons.append("deep_liquidity")
    elif liquidity_usd >= 250_000:
        score += 0.75
        reasons.append("healthy_liquidity")
    elif liquidity_usd < 25_000:
        score -= 1.5
        reasons.append("thin_liquidity")
    elif liquidity_usd < 5_000:
        score -= 2.5
        reasons.append("very_thin_liquidity")

    if liquidity_usd > 0:
        vol_ratio = volume_h24_usd / liquidity_usd
    else:
        vol_ratio = 0.0

    if vol_ratio >= 0.5:
        score += 0.5
        reasons.append("active_flow")
    elif vol_ratio < 0.01:
        score -= 0.5
        reasons.append("stale_pool")

    age_days = None
    if pair_created_at_ms and pair_created_at_ms > 0:
        age_days = (time.time() - (pair_created_at_ms / 1000.0)) / 86400.0
        if age_days < 3:
            score -= 1.5
            reasons.append("very_new_pool")
        elif age_days < 14:
            score -= 0.5
            reasons.append("new_pool")
        elif age_days >= 180:
            score += 0.5
            reasons.append("mature_pool")

    if min(t0_score, t1_score) <= 4 and max(t0_score, t1_score) >= 8:
        score -= 1.0
        reasons.append("quality_mismatch_tokens")

    score = round(clamp(score, 0.0, 10.0), 2)
    if score >= 9:
        tier = "high"
    elif score >= 7:
        tier = "medium"
    elif score >= 4:
        tier = "speculative"
    else:
        tier = "high-risk"

    return {
        "score": score,
        "tier": tier,
        "age_days": age_days,
        "reasons": sorted(set(reasons)),
    }


def compute_reward_apr_percent(reward_rate_per_sec: float, reward_token_price_usd: float, liquidity_usd: float) -> float:
    if reward_rate_per_sec <= 0 or reward_token_price_usd <= 0 or liquidity_usd <= 0:
        return 0.0
    apr = reward_rate_per_sec * SECONDS_PER_YEAR * reward_token_price_usd * 100.0 / liquidity_usd
    if not math.isfinite(apr):
        return 0.0
    return apr


def compute_fee_apr_percent(volume_24h_usd: float, fee_rate: float, liquidity_usd: float) -> float:
    if volume_24h_usd <= 0 or fee_rate <= 0 or liquidity_usd <= 0:
        return 0.0
    apr = volume_24h_usd * fee_rate * 365.0 * 100.0 / liquidity_usd
    if not math.isfinite(apr):
        return 0.0
    return apr


def compute_bribe_apr_percent(bribe_epoch_usd: float, liquidity_usd: float) -> float:
    if bribe_epoch_usd <= 0 or liquidity_usd <= 0:
        return 0.0
    apr = bribe_epoch_usd * 52.0 * 100.0 / liquidity_usd
    if not math.isfinite(apr):
        return 0.0
    return apr


def sort_pool_rows(rows: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
    if sort_by == "apr":
        key = lambda r: (to_float(r.get("total_apr_pct"), 0.0), to_float(r.get("safety_score"), 0.0), to_float(r.get("liquidity_usd"), 0.0))
    elif sort_by == "volume":
        key = lambda r: (to_float(r.get("volume_24h_usd"), 0.0), to_float(r.get("liquidity_usd"), 0.0), to_float(r.get("safety_score"), 0.0))
    elif sort_by == "liquidity":
        key = lambda r: (to_float(r.get("liquidity_usd"), 0.0), to_float(r.get("volume_24h_usd"), 0.0), to_float(r.get("safety_score"), 0.0))
    elif sort_by == "votes":
        key = lambda r: (to_float(r.get("vote_share_pct"), 0.0), to_float(r.get("liquidity_usd"), 0.0), to_float(r.get("safety_score"), 0.0))
    elif sort_by == "safety":
        key = lambda r: (to_float(r.get("safety_score"), 0.0), to_float(r.get("liquidity_usd"), 0.0), to_float(r.get("volume_24h_usd"), 0.0))
    else:
        raise ValueError(f"Unsupported sort_by: {sort_by}")
    return sorted(rows, key=key, reverse=True)


def fetch_markets_for_pools(pool_addresses: Sequence[str], workers: int) -> Dict[str, PairMarket]:
    out: Dict[str, PairMarket] = {}
    unique = sorted({normalize_address(p) for p in pool_addresses if normalize_address(p)})
    if not unique:
        return out

    def worker(addr: str) -> Tuple[str, Optional[PairMarket]]:
        return addr, fetch_pair_market(addr)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = [ex.submit(worker, addr) for addr in unique]
        for fut in as_completed(futures):
            addr, market = fut.result()
            if market:
                out[addr] = market
    return out


def read_bribe_epoch_rewards(
    cast: CastClient,
    bribe_addr: str,
    epoch_ts: int,
    max_tokens: int,
) -> List[Tuple[str, int]]:
    bribe = normalize_address(bribe_addr)
    if not bribe or is_zero_address(bribe):
        return []

    length_raw = cast.call(bribe, "rewardsListLength()(uint256)", allow_fail=True)
    if not length_raw:
        return []

    try:
        length = min(parse_cast_uint(length_raw), max_tokens)
    except Exception:
        return []

    rewards: List[Tuple[str, int]] = []
    for i in range(length):
        token_raw = cast.call(bribe, "bribeTokens(uint256)(address)", i, allow_fail=True)
        token_addr = parse_cast_address(token_raw or "")
        if not token_addr or is_zero_address(token_addr):
            continue
        amount_raw = cast.call(
            bribe,
            "tokenRewardsPerEpoch(address,uint256)(uint256)",
            token_addr,
            epoch_ts,
            allow_fail=True,
        )
        if not amount_raw:
            continue
        try:
            amount = parse_cast_uint(amount_raw)
        except Exception:
            amount = 0
        rewards.append((token_addr, amount))
    return rewards


def read_pool_tokens_and_fee(
    cast: CastClient,
    pool_address: str,
    pool_type: str,
    pair_factory_v2: str,
) -> Dict[str, Any]:
    pool = normalize_address(pool_address)
    out: Dict[str, Any] = {
        "token0": "",
        "token1": "",
        "fee_rate": 0.0,
        "fee_rate_source": "unknown",
        "fee_raw": None,
        "stable": None,
        "reserve0": None,
        "reserve1": None,
        "decimals0": None,
        "decimals1": None,
    }

    if pool_type == "v2":
        meta_raw = cast.call(
            pool,
            "metadata()(uint256,uint256,uint256,uint256,bool,address,address)",
            allow_fail=True,
        )
        if meta_raw:
            lines = [ln.strip() for ln in meta_raw.splitlines() if ln.strip()]
            if len(lines) >= 7:
                try:
                    out["decimals0"] = parse_cast_uint(lines[0])
                    out["decimals1"] = parse_cast_uint(lines[1])
                    out["reserve0"] = parse_cast_uint(lines[2])
                    out["reserve1"] = parse_cast_uint(lines[3])
                    out["stable"] = parse_cast_bool(lines[4])
                    out["token0"] = parse_cast_address(lines[5])
                    out["token1"] = parse_cast_address(lines[6])
                except Exception:
                    pass

        if not out["token0"]:
            out["token0"] = parse_cast_address(cast.call(pool, "token0()(address)", allow_fail=True) or "")
        if not out["token1"]:
            out["token1"] = parse_cast_address(cast.call(pool, "token1()(address)", allow_fail=True) or "")
        if out["stable"] is None:
            stable_raw = cast.call(pool, "stable()(bool)", allow_fail=True)
            if stable_raw:
                try:
                    out["stable"] = parse_cast_bool(stable_raw)
                except Exception:
                    out["stable"] = False

        stable_flag = bool(out["stable"]) if out["stable"] is not None else False
        fee_raw = cast.call(
            pair_factory_v2,
            "getFee(address,bool)(uint256)",
            pool,
            stable_flag,
            allow_fail=True,
        )
        if fee_raw:
            try:
                raw = parse_cast_uint(fee_raw)
                out["fee_raw"] = raw
                out["fee_rate"] = raw / 10_000.0
                out["fee_rate_source"] = "pair_factory_getFee_bps_assumed"
            except Exception:
                pass
    else:
        out["token0"] = parse_cast_address(cast.call(pool, "token0()(address)", allow_fail=True) or "")
        out["token1"] = parse_cast_address(cast.call(pool, "token1()(address)", allow_fail=True) or "")

        fee_raw = cast.call(pool, "fee()(uint16)", allow_fail=True)
        if fee_raw:
            try:
                raw = parse_cast_uint(fee_raw)
                out["fee_raw"] = raw
                out["fee_rate"] = raw / 1_000_000.0
                out["fee_rate_source"] = "algebra_fee_1e6"
            except Exception:
                pass

        reserves_raw = cast.call(pool, "getReserves()(uint128,uint128)", allow_fail=True)
        if reserves_raw:
            lines = [ln.strip() for ln in reserves_raw.splitlines() if ln.strip()]
            if len(lines) >= 2:
                try:
                    out["reserve0"] = parse_cast_uint(lines[0])
                    out["reserve1"] = parse_cast_uint(lines[1])
                except Exception:
                    pass

    return out


def enumerate_factory_pools(cast: CastClient, factory: str) -> List[str]:
    factory_addr = normalize_address(factory)
    if not factory_addr:
        return []
    length_raw = cast.call(factory_addr, "allPairsLength()(uint256)", allow_fail=True)
    if not length_raw:
        return []

    try:
        length = parse_cast_uint(length_raw)
    except Exception:
        return []

    pools: List[str] = []
    for i in range(length):
        addr_raw = cast.call(factory_addr, "allPairs(uint256)(address)", i, allow_fail=True)
        addr = parse_cast_address(addr_raw or "")
        if addr:
            pools.append(addr)
    return pools


def format_usd(value: float) -> str:
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value:,.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Supernova pools and rank by APR, liquidity, volume, vote weight, and safety.",
    )
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL, help=f"Ethereum JSON-RPC URL (default: {DEFAULT_RPC_URL})")
    parser.add_argument("--gauge-manager", default=DEFAULT_GAUGE_MANAGER, help="GaugeManager proxy address")
    parser.add_argument("--voter", default=DEFAULT_VOTER, help="Voter contract address")
    parser.add_argument("--voting-escrow", default=DEFAULT_VOTING_ESCROW, help="VotingEscrow contract address")
    parser.add_argument("--rewards-distributor", default=DEFAULT_REWARDS_DISTRIBUTOR, help="RewardsDistributor contract address")
    parser.add_argument("--nova-token", default=DEFAULT_NOVA_TOKEN, help="NOVA token address")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent worker count for pool enrichment (default: 8)")
    parser.add_argument("--http-workers", type=int, default=8, help="Concurrent worker count for Dex API calls (default: 8)")
    parser.add_argument("--max-pools", type=int, default=0, help="Limit number of pools for fast local simulations (0 = all)")
    parser.add_argument("--bribe-token-cap", type=int, default=4, help="Max bribe tokens to read per bribe contract (default: 4)")
    parser.add_argument("--skip-bribes", action="store_true", help="Skip bribe token scans for faster runs")
    parser.add_argument("--progress-every", type=int, default=5, help="Print progress every N completed pools (default: 5)")
    parser.add_argument(
        "--sort-by",
        choices=["apr", "volume", "liquidity", "votes", "safety"],
        default="apr",
        help="Primary ranking key (default: apr)",
    )
    parser.add_argument("--min-liquidity-usd", type=float, default=0.0, help="Drop pools below this liquidity threshold")
    parser.add_argument("--only-alive", action="store_true", help="Keep only pools with live gauges")
    parser.add_argument("--strict", action="store_true", help="Fail if validation rails detect inconsistencies")
    parser.add_argument("--out-json", default="supernova_pool_intel_report.json", help="JSON output path")
    parser.add_argument("--out-csv", default="supernova_pool_intel_report.csv", help="CSV output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_cast()

    cast = CastClient(args.rpc_url, timeout_sec=12)

    gauge_manager = normalize_address(args.gauge_manager)
    voter = normalize_address(args.voter)
    voting_escrow = normalize_address(args.voting_escrow)
    rewards_distributor = normalize_address(args.rewards_distributor)
    nova_token = normalize_address(args.nova_token)

    if not all([gauge_manager, voter, voting_escrow, rewards_distributor, nova_token]):
        raise RuntimeError("One or more contract addresses are invalid.")

    pair_factory_v2 = parse_cast_address(cast.call(gauge_manager, "pairFactory()(address)", allow_fail=False) or "")
    pair_factory_cl = parse_cast_address(cast.call(gauge_manager, "pairFactoryCL()(address)", allow_fail=False) or "")

    if not pair_factory_v2 or not pair_factory_cl:
        raise RuntimeError("Failed to resolve pair factories from GaugeManager.")

    print(f"[scan] gaugeManager={gauge_manager}")
    print(f"[scan] pairFactory(v2)={pair_factory_v2}")
    print(f"[scan] pairFactory(CL)={pair_factory_cl}")

    pools_v2 = enumerate_factory_pools(cast, pair_factory_v2)
    pools_cl = enumerate_factory_pools(cast, pair_factory_cl)

    pool_rows: List[Tuple[str, str]] = [(p, "v2") for p in pools_v2] + [(p, "cl") for p in pools_cl]
    pool_rows = sorted({(p, t) for p, t in pool_rows})

    if args.max_pools and args.max_pools > 0:
        pool_rows = pool_rows[: args.max_pools]

    if not pool_rows:
        raise RuntimeError("No pools discovered from factories.")

    print(f"[scan] pools discovered: total={len(pool_rows)} (v2={len(pools_v2)} cl={len(pools_cl)})")

    markets = fetch_markets_for_pools([p for p, _ in pool_rows], workers=args.http_workers)

    token_price_cache: Dict[str, Tuple[Optional[float], Optional[str]]] = {}
    token_meta_cache: Dict[str, TokenMeta] = {}
    cache_lock = threading.Lock()

    nova_price_usd, nova_price_source = fetch_token_spot_price_usd(nova_token)
    with cache_lock:
        token_price_cache[nova_token] = (nova_price_usd, nova_price_source)

    ve_supply_raw = cast.call(voting_escrow, "supply()(uint256)", allow_fail=True) or "0"
    ve_permanent_raw = cast.call(voting_escrow, "permanentLockBalance()(uint256)", allow_fail=True) or "0"
    ve_smnft_raw = cast.call(voting_escrow, "smNFTBalance()(uint256)", allow_fail=True) or "0"

    ve_supply = parse_cast_uint(ve_supply_raw)
    ve_permanent = parse_cast_uint(ve_permanent_raw)
    ve_smnft = parse_cast_uint(ve_smnft_raw)

    total_weight_raw = cast.call(voter, "totalWeight()(uint256)", allow_fail=True) or "0"
    total_weight = parse_cast_uint(total_weight_raw)

    now_ts = int(time.time())
    current_epoch = epoch_start(now_ts)

    distributor_epoch_tokens_raw = cast.call(
        rewards_distributor,
        "tokens_per_week(uint256)(uint256)",
        current_epoch,
        allow_fail=True,
    ) or "0"
    distributor_epoch_tokens = parse_cast_uint(distributor_epoch_tokens_raw)

    protocol_tvl_usd, protocol_tvl_latest, protocol_tvl_latest_ts = fetch_protocol_tvl_usd()

    def build_pool_record(pool_addr: str, pool_type: str) -> Dict[str, Any]:
        warnings: List[str] = []
        pool = normalize_address(pool_addr)
        market = markets.get(pool)

        token_info = read_pool_tokens_and_fee(
            cast=cast,
            pool_address=pool,
            pool_type=pool_type,
            pair_factory_v2=pair_factory_v2,
        )

        token0_addr = normalize_address(token_info.get("token0"))
        token1_addr = normalize_address(token_info.get("token1"))

        fallback0_symbol = ""
        fallback0_name = ""
        fallback1_symbol = ""
        fallback1_name = ""

        if market:
            if token0_addr and token0_addr == market.base_token_address:
                fallback0_symbol = market.base_token_symbol
                fallback0_name = market.base_token_name
                fallback1_symbol = market.quote_token_symbol
                fallback1_name = market.quote_token_name
            elif token0_addr and token0_addr == market.quote_token_address:
                fallback0_symbol = market.quote_token_symbol
                fallback0_name = market.quote_token_name
                fallback1_symbol = market.base_token_symbol
                fallback1_name = market.base_token_name
            else:
                fallback0_symbol = market.base_token_symbol
                fallback0_name = market.base_token_name
                fallback1_symbol = market.quote_token_symbol
                fallback1_name = market.quote_token_name

        token0 = read_token_meta(
            cast,
            token0_addr,
            token_price_cache,
            token_meta_cache,
            cache_lock,
            fallback_symbol=fallback0_symbol,
            fallback_name=fallback0_name,
        )
        token1 = read_token_meta(
            cast,
            token1_addr,
            token_price_cache,
            token_meta_cache,
            cache_lock,
            fallback_symbol=fallback1_symbol,
            fallback_name=fallback1_name,
        )

        gauge = parse_cast_address(cast.call(gauge_manager, "gauges(address)(address)", pool, allow_fail=True) or "")
        is_gauged = bool(gauge and not is_zero_address(gauge))
        is_alive = False
        if is_gauged:
            alive_raw = cast.call(gauge_manager, "isGaugeAliveForPool(address)(bool)", pool, allow_fail=True)
            if alive_raw:
                try:
                    is_alive = parse_cast_bool(alive_raw)
                except Exception:
                    is_alive = False

        vote_weight_raw = cast.call(voter, "weights(address)(uint256)", pool, allow_fail=True) or "0"
        vote_weight = parse_cast_uint(vote_weight_raw)

        reward_rate_raw = "0"
        reward_for_duration_raw = "0"
        gauge_supply_raw = None
        reward_rate = 0
        reward_for_duration = 0
        gauge_supply = None

        internal_bribe = ""
        external_bribe = ""
        bribe_entries: List[Dict[str, Any]] = []
        bribe_epoch_usd = 0.0

        if is_gauged:
            reward_rate_raw = cast.call(gauge, "rewardRate()(uint256)", allow_fail=True) or "0"
            reward_for_duration_raw = cast.call(gauge, "rewardForDuration()(uint256)", allow_fail=True) or "0"
            reward_rate = parse_cast_uint(reward_rate_raw)
            reward_for_duration = parse_cast_uint(reward_for_duration_raw)

            gauge_supply_raw = cast.call(gauge, "totalActiveSupply()(uint256)", allow_fail=True)
            if gauge_supply_raw:
                gauge_supply = parse_cast_uint(gauge_supply_raw)
            else:
                gauge_supply_raw = cast.call(gauge, "totalSupply()(uint256)", allow_fail=True)
                if gauge_supply_raw:
                    gauge_supply = parse_cast_uint(gauge_supply_raw)

            internal_bribe = parse_cast_address(cast.call(gauge_manager, "internal_bribes(address)(address)", gauge, allow_fail=True) or "")
            external_bribe = parse_cast_address(cast.call(gauge_manager, "external_bribes(address)(address)", gauge, allow_fail=True) or "")

            if not args.skip_bribes:
                for label, bribe_addr in (("internal", internal_bribe), ("external", external_bribe)):
                    rewards = read_bribe_epoch_rewards(cast, bribe_addr, current_epoch, max_tokens=max(1, args.bribe_token_cap))
                    for reward_token_addr, reward_amount_raw in rewards:
                        reward_meta = read_token_meta(
                            cast,
                            reward_token_addr,
                            token_price_cache,
                            token_meta_cache,
                            cache_lock,
                        )
                        amount_tokens = reward_amount_raw / (10 ** max(0, reward_meta.decimals))
                        price = reward_meta.price_usd or 0.0
                        usd = amount_tokens * price
                        bribe_epoch_usd += usd
                        bribe_entries.append(
                            {
                                "bribe_type": label,
                                "bribe_contract": bribe_addr,
                                "token": reward_meta.symbol,
                                "token_address": reward_meta.address,
                                "amount_tokens": amount_tokens,
                                "amount_raw": reward_amount_raw,
                                "price_usd": price,
                                "value_usd": usd,
                            }
                        )

        liquidity_usd = market.liquidity_usd if market else 0.0
        volume_h24_usd = market.volume_h24_usd if market else 0.0
        txns_h24 = market.txns_h24 if market else 0

        reserve0 = token_info.get("reserve0")
        reserve1 = token_info.get("reserve1")
        dec0 = token_info.get("decimals0") if token_info.get("decimals0") is not None else token0.decimals
        dec1 = token_info.get("decimals1") if token_info.get("decimals1") is not None else token1.decimals

        if liquidity_usd <= 0 and reserve0 is not None and reserve1 is not None:
            price0 = token0.price_usd or 0.0
            price1 = token1.price_usd or 0.0
            amount0 = reserve0 / (10 ** max(0, int(dec0 or 18)))
            amount1 = reserve1 / (10 ** max(0, int(dec1 or 18)))
            inferred_liq = (amount0 * price0) + (amount1 * price1)
            if inferred_liq > 0:
                liquidity_usd = inferred_liq
                warnings.append("liquidity_inferred_from_reserves")

        fee_rate = to_float(token_info.get("fee_rate"), default=0.0)
        fee_rate_source = token_info.get("fee_rate_source") or "unknown"

        reward_apr = compute_reward_apr_percent(
            reward_rate_per_sec=reward_rate / 1e18,
            reward_token_price_usd=nova_price_usd or 0.0,
            liquidity_usd=liquidity_usd,
        )
        fee_apr = compute_fee_apr_percent(
            volume_24h_usd=volume_h24_usd,
            fee_rate=fee_rate,
            liquidity_usd=liquidity_usd,
        )
        bribe_apr = compute_bribe_apr_percent(
            bribe_epoch_usd=bribe_epoch_usd,
            liquidity_usd=liquidity_usd,
        )
        total_apr = reward_apr + fee_apr + bribe_apr

        safety = score_pool_safety(
            token0=token0,
            token1=token1,
            liquidity_usd=liquidity_usd,
            volume_h24_usd=volume_h24_usd,
            pair_created_at_ms=market.pair_created_at_ms if market else None,
        )

        vote_share_pct = safe_div(float(vote_weight), float(total_weight)) * 100.0 if total_weight else 0.0

        if not token0_addr or not token1_addr:
            warnings.append("missing_pool_tokens")
        if liquidity_usd <= 0:
            warnings.append("missing_liquidity")

        created_at_iso = None
        if market and market.pair_created_at_ms:
            try:
                created_at_iso = dt.datetime.fromtimestamp(market.pair_created_at_ms / 1000, tz=dt.timezone.utc).isoformat()
            except Exception:
                created_at_iso = None

        return {
            "pool_address": pool,
            "pool_type": pool_type,
            "dex_id": market.dex_id if market else None,
            "pair_url": market.pair_url if market else None,
            "pair_created_at": created_at_iso,
            "token0_address": token0.address,
            "token0_symbol": token0.symbol,
            "token0_name": token0.name,
            "token1_address": token1.address,
            "token1_symbol": token1.symbol,
            "token1_name": token1.name,
            "is_gauged": is_gauged,
            "is_gauge_alive": is_alive,
            "gauge_address": gauge or None,
            "gauge_supply": gauge_supply,
            "internal_bribe": internal_bribe or None,
            "external_bribe": external_bribe or None,
            "vote_weight": vote_weight,
            "vote_share_pct": vote_share_pct,
            "liquidity_usd": liquidity_usd,
            "volume_24h_usd": volume_h24_usd,
            "txns_24h": txns_h24,
            "fee_rate": fee_rate,
            "fee_rate_source": fee_rate_source,
            "fee_rate_raw": token_info.get("fee_raw"),
            "reward_rate_nova_per_sec": reward_rate / 1e18,
            "reward_rate_nova_per_day": (reward_rate / 1e18) * 86400.0,
            "reward_for_duration_nova": reward_for_duration / 1e18,
            "bribe_epoch_usd": bribe_epoch_usd,
            "reward_apr_pct": reward_apr,
            "fee_apr_pct": fee_apr,
            "bribe_apr_pct": bribe_apr,
            "total_apr_pct": total_apr,
            "safety_score": safety["score"],
            "safety_tier": safety["tier"],
            "safety_reasons": safety.get("reasons") or [],
            "bribe_rewards": bribe_entries,
            "warnings": warnings,
        }

    records: List[Dict[str, Any]] = []
    progress_every = max(1, args.progress_every)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(build_pool_record, pool, ptype) for pool, ptype in pool_rows]
        completed = 0
        total = len(futures)
        for fut in as_completed(futures):
            records.append(fut.result())
            completed += 1
            if completed == total or completed % progress_every == 0:
                print(f"[scan] progress: {completed}/{total} pools completed")

    if args.only_alive:
        records = [r for r in records if r.get("is_gauge_alive")]

    if args.min_liquidity_usd > 0:
        records = [r for r in records if to_float(r.get("liquidity_usd"), default=0.0) >= args.min_liquidity_usd]

    records = sort_pool_rows(records, args.sort_by)

    for idx, row in enumerate(records, start=1):
        row["rank"] = idx

    if args.strict:
        strict_errors: List[str] = []
        if not records:
            strict_errors.append("No records after filtering.")
        for row in records:
            for field in ("reward_apr_pct", "fee_apr_pct", "bribe_apr_pct", "total_apr_pct", "safety_score"):
                val = to_float(row.get(field), default=float("nan"))
                if not math.isfinite(val):
                    strict_errors.append(f"Non-finite value in {field} for {row.get('pool_address')}")

        for row in records:
            t0 = normalize_address(row.get("token0_address"))
            t1 = normalize_address(row.get("token1_address"))
            is_eth_usdc = (is_official_eth(t0) and is_official_usdc(t1)) or (is_official_eth(t1) and is_official_usdc(t0))
            if is_eth_usdc and to_float(row.get("safety_score"), default=0.0) < 10.0:
                strict_errors.append(f"ETH/USDC pool {row.get('pool_address')} is not scored 10/10")

        if strict_errors:
            raise RuntimeError("Strict validation failed:\n- " + "\n- ".join(strict_errors[:20]))

    gauged = sum(1 for r in records if r.get("is_gauged"))
    alive = sum(1 for r in records if r.get("is_gauge_alive"))

    total_liquidity = sum(to_float(r.get("liquidity_usd"), default=0.0) for r in records)
    total_volume = sum(to_float(r.get("volume_24h_usd"), default=0.0) for r in records)

    safety_distribution = {
        "high": sum(1 for r in records if r.get("safety_tier") == "high"),
        "medium": sum(1 for r in records if r.get("safety_tier") == "medium"),
        "speculative": sum(1 for r in records if r.get("safety_tier") == "speculative"),
        "high-risk": sum(1 for r in records if r.get("safety_tier") == "high-risk"),
    }

    ve_locked_nova = ve_supply / 1e18
    ve_locked_value_usd = (nova_price_usd or 0.0) * ve_locked_nova
    distributor_epoch_nova = distributor_epoch_tokens / 1e18
    distributor_epoch_usd = (nova_price_usd or 0.0) * distributor_epoch_nova

    report = {
        "generated_at_utc": now_iso_utc(),
        "inputs": {
            "rpc_url": args.rpc_url,
            "gauge_manager": gauge_manager,
            "voter": voter,
            "voting_escrow": voting_escrow,
            "rewards_distributor": rewards_distributor,
            "nova_token": nova_token,
            "sort_by": args.sort_by,
            "max_pools": args.max_pools,
            "min_liquidity_usd": args.min_liquidity_usd,
            "only_alive": args.only_alive,
            "bribe_token_cap": args.bribe_token_cap,
            "skip_bribes": args.skip_bribes,
            "progress_every": args.progress_every,
        },
        "protocol_summary": {
            "pair_factory_v2": pair_factory_v2,
            "pair_factory_cl": pair_factory_cl,
            "pool_count_scanned": len(records),
            "gauged_pool_count": gauged,
            "live_gauge_pool_count": alive,
            "total_liquidity_usd": total_liquidity,
            "total_volume_24h_usd": total_volume,
            "safety_distribution": safety_distribution,
            "nova_price_usd": nova_price_usd,
            "nova_price_source": nova_price_source,
            "ve_locked_nova": ve_locked_nova,
            "ve_locked_value_usd": ve_locked_value_usd,
            "ve_permanent_locked_nova": ve_permanent / 1e18,
            "ve_smnft_balance": ve_smnft / 1e18,
            "total_vote_weight": total_weight,
            "current_epoch_start": current_epoch,
            "rewards_distributor_epoch_nova": distributor_epoch_nova,
            "rewards_distributor_epoch_value_usd": distributor_epoch_usd,
            "protocol_tvl_usd": protocol_tvl_usd,
            "protocol_tvl_latest_point_usd": protocol_tvl_latest,
            "protocol_tvl_latest_point_timestamp": protocol_tvl_latest_ts,
        },
        "pools": records,
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "rank",
        "pool_address",
        "pool_type",
        "dex_id",
        "token0_symbol",
        "token1_symbol",
        "is_gauged",
        "is_gauge_alive",
        "liquidity_usd",
        "volume_24h_usd",
        "fee_rate",
        "reward_apr_pct",
        "fee_apr_pct",
        "bribe_apr_pct",
        "total_apr_pct",
        "vote_share_pct",
        "safety_score",
        "safety_tier",
        "pair_created_at",
        "pair_url",
        "warnings",
        "safety_reasons",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=csv_fields)
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    **{k: row.get(k) for k in csv_fields},
                    "warnings": ";".join(row.get("warnings") or []),
                    "safety_reasons": ";".join(row.get("safety_reasons") or []),
                }
            )

    top_preview = records[: min(10, len(records))]
    print("\nTop pools:")
    for row in top_preview:
        print(
            f"#{row['rank']:>2} {row['token0_symbol']}/{row['token1_symbol']} "
            f"APR={format_pct(to_float(row['total_apr_pct']))} "
            f"Liq={format_usd(to_float(row['liquidity_usd']))} "
            f"Vol24h={format_usd(to_float(row['volume_24h_usd']))} "
            f"Safety={row['safety_score']}/10 ({row['safety_tier']})"
        )

    print("\nSummary:")
    print(f"- Pools scanned: {len(records)}")
    print(f"- Gauged pools: {gauged} (alive: {alive})")
    print(f"- Total liquidity: {format_usd(total_liquidity)}")
    print(f"- Total 24h volume: {format_usd(total_volume)}")
    if nova_price_usd:
        print(f"- NOVA spot: ${nova_price_usd:.6f}")
    if protocol_tvl_usd:
        print(f"- DefiLlama TVL: {format_usd(protocol_tvl_usd)}")
    print(f"- Output JSON: {out_json}")
    print(f"- Output CSV: {out_csv}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
