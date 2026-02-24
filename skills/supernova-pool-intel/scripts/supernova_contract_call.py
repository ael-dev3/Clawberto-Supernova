#!/usr/bin/env python3
"""
Read-only contract-call helper for Supernova analysis.

Examples:
  python3 skills/supernova-pool-intel/scripts/supernova_contract_call.py --list-core
  python3 skills/supernova-pool-intel/scripts/supernova_contract_call.py \
    --to 0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2 \
    --sig 'length()(uint256)'
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
SIGNATURE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\([^)]*\)\([^)]*\)$")

DEFAULT_RPC_URL = "https://ethereum.publicnode.com"

CORE_ADDRESSES = {
    "gauge_manager": "0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2",
    "voter": "0x1c7bf2532dfa34eeea02c3759e0ca8d87b1d8171",
    "voting_escrow": "0x4c3e7640b3e3a39a2e5d030a0c1412d80fee1d44",
    "rewards_distributor": "0xb3410a30af5033af822b8ea5ad3bd0a19490ea97",
    "nova_token": "0x00da8466b296e382e5da2bf20962d0cb87200c78",
    "pair_factory_v2": "0x5aef44edfc5a7edd30826c724ea12d7be15bdc30",
    "pair_factory_cl": "0x44b7fbd4d87149efa5347c451e74b9fd18e89c55",
}


def normalize_address(value: str) -> str:
    text = str(value or "").strip()
    if ADDRESS_RE.match(text):
        return text.lower()
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a safe read-only contract call with cast.")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL, help=f"Ethereum RPC URL (default: {DEFAULT_RPC_URL})")
    parser.add_argument("--to", default="", help="Target contract address")
    parser.add_argument("--sig", default="", help="Function signature, e.g. 'length()(uint256)'")
    parser.add_argument("--arg", action="append", default=[], help="Call argument (repeatable)")
    parser.add_argument("--allow-any-address", action="store_true", help="Allow calls to addresses outside known Supernova addresses")
    parser.add_argument("--list-core", action="store_true", help="Print core Supernova addresses and exit")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser.parse_args()


def ensure_cast() -> None:
    proc = subprocess.run(
        ["cast", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cast is not available: {proc.stderr.strip()}")


def load_known_addresses(repo_root: Path) -> Set[str]:
    known: Set[str] = set(normalize_address(v) for v in CORE_ADDRESSES.values())
    csv_path = repo_root / "metadata" / "live_contracts_eth_mainnet.csv"
    if not csv_path.exists():
        return {a for a in known if a}

    with csv_path.open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            addr = normalize_address(row.get("address") or "")
            if addr:
                known.add(addr)
    return known


def run_cast_call(rpc_url: str, to: str, signature: str, args: List[str]) -> str:
    cmd = ["cast", "call", "--rpc-url", rpc_url, to, signature, *args]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "unknown cast error")
    return proc.stdout.strip()


def main() -> int:
    args = parse_args()

    ensure_cast()

    parsed = urllib.parse.urlparse(args.rpc_url)
    if parsed.scheme != "https":
        raise RuntimeError(f"RPC URL must be https for safety, got: {args.rpc_url}")

    repo_root = Path(__file__).resolve().parents[3]
    known_addresses = load_known_addresses(repo_root)

    if args.list_core:
        payload: Dict[str, Any] = {
            "core_addresses": CORE_ADDRESSES,
            "known_contract_count": len(known_addresses),
        }
        print(json.dumps(payload, indent=2))
        return 0

    target = normalize_address(args.to)
    if not target:
        raise RuntimeError("--to must be a valid 0x contract address")

    if not args.allow_any_address and target not in known_addresses:
        raise RuntimeError(
            "Blocked address: not in known Supernova contract registry. "
            "Use --allow-any-address only when you intentionally need off-registry reads."
        )

    signature = args.sig.strip()
    if not SIGNATURE_RE.match(signature):
        raise RuntimeError(
            "Invalid --sig format. Expected 'fn(type,...)(ret,...)', "
            "for example: 'weights(address)(uint256)'"
        )

    output = run_cast_call(args.rpc_url, target, signature, args.arg)

    if args.json:
        payload = {
            "rpc_url": args.rpc_url,
            "to": target,
            "signature": signature,
            "args": args.arg,
            "result_raw": output,
            "result_lines": [ln.strip() for ln in output.splitlines() if ln.strip()],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(output)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
