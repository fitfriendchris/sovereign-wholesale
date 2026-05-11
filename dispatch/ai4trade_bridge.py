#!/usr/bin/env python3
"""ai4trade_bridge.py — Bridge Omni ICT signals to AI4Trade platform.

Usage:
    python3 ai4trade_bridge.py --publish-signals
    python3 ai4trade_bridge.py --follow-top N
    python3 ai4trade_bridge.py --get-positions
    python3 ai4trade_bridge.py --heartbeat
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Token stored by Sovereign registration
TOKEN_FILE = Path.home() / "Desktop" / "Sovereign" / "state" / "ai4trade_token.json"
SIGNALS_FILE = Path.home() / "Omni-full-ALGO-Trading-Bot" / "shared" / "signals.json"
OMNI_PNL_FILE = Path.home() / "Omni-full-ALGO-Trading-Bot" / "shared" / "omni_pnl.json"

BASE_URL = "https://ai4trade.ai/api"


def load_token() -> str:
    if not TOKEN_FILE.exists():
        raise RuntimeError(f"Token file not found: {TOKEN_FILE}")
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    return data.get("token") or data.get("data", {}).get("token")


def headers() -> dict:
    return {"Authorization": f"Bearer {load_token()}", "Content-Type": "application/json"}


def read_omni_signals() -> list[dict]:
    """Read current Omni signals from shared file."""
    if not SIGNALS_FILE.exists():
        return []
    with open(SIGNALS_FILE) as f:
        data = json.load(f)
    return data.get("signals", [])


def publish_signal(signal: dict) -> dict:
    """Publish an Omni signal to AI4Trade as a realtime trade."""
    symbol = signal.get("symbol", "XAUUSD")
    direction = signal.get("direction", "BULL")
    action = "buy" if direction == "BULL" else "sell"
    
    payload = {
        "market": "crypto",
        "action": action,
        "symbol": symbol,
        "price": signal.get("entry_price") or 0,
        "quantity": 0.1,
        "content": f"Omni ICT Signal: {direction} on {symbol} {signal.get('timeframe', 'M5')} | Confidence: {signal.get('confidence', 0)} | Scale: {signal.get('scale_action', 'HOLD')}",
        "executed_at": signal.get("ts", datetime.now(timezone.utc).isoformat())
    }
    
    resp = requests.post(f"{BASE_URL}/signals/realtime", headers=headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def publish_strategy(title: str, content: str, symbols: list[str] | None = None) -> dict:
    """Publish a strategy analysis post."""
    payload = {
        "market": "crypto",
        "title": title,
        "content": content,
        "symbols": symbols or ["XAUUSD", "XAGUSD"],
        "tags": ["omni", "ict", "algo-trading", "gold", "silver"]
    }
    resp = requests.post(f"{BASE_URL}/signals/strategy", headers=headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def follow_trader(leader_id: int) -> dict:
    """Follow a trader by ID."""
    resp = requests.post(f"{BASE_URL}/signals/follow", headers=headers(), json={"leader_id": leader_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_top_traders(limit: int = 10) -> list[dict]:
    """Get top traders by signal count."""
    resp = requests.get(f"{BASE_URL}/signals/grouped?limit={limit}", headers=headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("agents", [])


def get_positions() -> list[dict]:
    """Get our current positions."""
    resp = requests.get(f"{BASE_URL}/positions", headers=headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("positions", [])


def heartbeat() -> dict:
    """Poll for notifications."""
    resp = requests.post(f"{BASE_URL}/claw/agents/heartbeat", headers=headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_signal_feed(limit: int = 20) -> list[dict]:
    """Get recent signal feed."""
    resp = requests.get(f"{BASE_URL}/signals/feed?limit={limit}", headers=headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("signals", [])


def main() -> int:
    p = argparse.ArgumentParser(description="AI4Trade bridge for Omni/Sovereign")
    p.add_argument("--publish-signals", action="store_true", help="Publish current Omni signals")
    p.add_argument("--publish-strategy", type=str, metavar="TITLE", help="Publish strategy with title")
    p.add_argument("--follow-top", type=int, metavar="N", help="Follow top N traders")
    p.add_argument("--follow-id", type=int, metavar="ID", help="Follow specific trader ID")
    p.add_argument("--positions", action="store_true", help="Get current positions")
    p.add_argument("--heartbeat", action="store_true", help="Poll heartbeat")
    p.add_argument("--feed", type=int, metavar="N", default=0, help="Get N recent signals")
    p.add_argument("--status", action="store_true", help="Show agent status")
    args = p.parse_args()
    
    if args.status:
        resp = requests.get(f"{BASE_URL}/claw/agents/me", headers=headers(), timeout=10)
        print(json.dumps(resp.json(), indent=2))
        return 0
    
    if args.publish_signals:
        signals = read_omni_signals()
        if not signals:
            print("No Omni signals found.")
            return 1
        published = 0
        for sig in signals:
            try:
                result = publish_signal(sig)
                print(f"Published: {sig.get('symbol')} {sig.get('direction')} — ID {result.get('id', 'N/A')}")
                published += 1
            except Exception as e:
                print(f"Failed {sig.get('symbol')}: {e}")
        print(f"\nTotal published: {published}/{len(signals)}")
        return 0
    
    if args.publish_strategy:
        content = f"Omni ICT Algo Trading — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        content += "Automated XAUUSD/XAGUSD trading using ICT concepts:\n"
        content += "- Order block detection\n"
        content += "- Liquidity sweep + reversal\n"
        content += "- Multi-timeframe bias alignment\n"
        content += "- Dynamic position scaling\n\n"
        content += "Follow for real-time signals."
        
        result = publish_strategy(args.publish_strategy, content)
        print(f"Strategy published: ID {result.get('id', 'N/A')}")
        return 0
    
    if args.follow_top:
        traders = get_top_traders(args.follow_top * 2)
        followed = 0
        for trader in traders[:args.follow_top]:
            try:
                result = follow_trader(trader["agent_id"])
                print(f"Followed: {trader['agent_name']} ({trader.get('signal_count', 0)} signals)")
                followed += 1
            except Exception as e:
                print(f"Failed to follow {trader['agent_name']}: {e}")
        print(f"\nTotal followed: {followed}")
        return 0
    
    if args.follow_id:
        result = follow_trader(args.follow_id)
        print(f"Followed trader ID {args.follow_id}: {result}")
        return 0
    
    if args.positions:
        positions = get_positions()
        print(f"Positions: {len(positions)}")
        for pos in positions:
            print(f"  {pos.get('symbol')} {pos.get('quantity')} @ {pos.get('entry_price')} (PnL: ${pos.get('pnl', 0):.2f})")
        return 0
    
    if args.heartbeat:
        result = heartbeat()
        msgs = result.get("messages", [])
        tasks = result.get("tasks", [])
        print(f"Messages: {len(msgs)}, Tasks: {len(tasks)}, Unread: {result.get('unread_count', 0)}")
        for m in msgs[:3]:
            print(f"  [{m.get('type')}] {m.get('content', '')[:100]}")
        return 0
    
    if args.feed > 0:
        signals = get_signal_feed(args.feed)
        print(f"Recent signals ({len(signals)}):")
        for s in signals:
            print(f"  [{s.get('agent_name')}] {s.get('title') or s.get('symbol')} | {s.get('side') or s.get('signal_type')}")
        return 0
    
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
