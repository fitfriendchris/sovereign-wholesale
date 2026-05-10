"""Minimal OpenRouter client.

`chat(model, system, user)` returns text. Handles:
- API key from .env (OPENROUTER_API_KEY)
- Retry with backoff on 429/5xx
- Cost tracking written to revenue.json (api_budget_usd) via dispatch.registry
- A `--ping` CLI for the smoke test (1-token request, ~$0.0001)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

# Lazy-loaded so we don't fail import when keys are absent (smoke tests).
_API_KEY = None
_DOTENV_LOADED = False


def _load_env() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_api_key() -> str:
    global _API_KEY
    if _API_KEY:
        return _API_KEY
    _load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment or .env")
    _API_KEY = key
    return key


# Default model aliases — adjust as OpenRouter's catalog evolves.
MODEL_ALIASES = {
    "haiku-4.5": "anthropic/claude-haiku-4.5",
    "sonnet-4.6": "anthropic/claude-sonnet-4.6",
    "opus-4.7": "anthropic/claude-opus-4.7",
    "kimi-k2": "moonshotai/kimi-k2",
    "kimi-2.6": "moonshotai/kimi-k2-0905",
}


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


def chat(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    timeout: int = 60,
    track_cost: bool = True,
) -> dict:
    """Send a single chat request. Returns dict with `text`, `usage`, `cost_usd`."""
    body = {
        "model": resolve_model(model),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {_get_api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sovereign.local",
            "X-Title": "Sovereign Multi-Agent Orchestrator",
        },
        method="POST",
    )

    attempts = 0
    last_err: Exception | None = None
    while attempts < 4:
        attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            cost = float(data.get("cost", 0)) or _estimate_cost(model, usage)
            if track_cost and cost > 0:
                _track_cost(cost)
            return {"text": text, "usage": usage, "cost_usd": cost, "raw": data}
        except urllib.error.HTTPError as e:
            last_err = e
            status = e.code
            if status in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempts, 30))
                continue
            # Non-retryable — surface details
            try:
                body_text = e.read().decode()
            except Exception:
                body_text = ""
            raise RuntimeError(f"openrouter {status}: {body_text}") from e
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(min(2 ** attempts, 30))
            continue
    raise RuntimeError(f"openrouter failed after {attempts} attempts: {last_err}")


def _estimate_cost(model: str, usage: dict) -> float:
    """Rough fallback when OpenRouter doesn't return cost in the response.

    Per-token rates are best-effort; OpenRouter's billing dashboard is canonical.
    """
    rates_per_1k = {
        "anthropic/claude-haiku-4.5":  (0.001, 0.005),
        "anthropic/claude-sonnet-4.6": (0.003, 0.015),
        "anthropic/claude-opus-4.7":   (0.015, 0.075),
        "moonshotai/kimi-k2":          (0.0006, 0.0025),
        "moonshotai/kimi-k2-0905":     (0.0006, 0.0025),
    }
    m = resolve_model(model)
    if m not in rates_per_1k:
        return 0.0
    in_rate, out_rate = rates_per_1k[m]
    p = usage.get("prompt_tokens", 0) / 1000.0
    c = usage.get("completion_tokens", 0) / 1000.0
    return round(p * in_rate + c * out_rate, 6)


def _track_cost(cost_usd: float) -> None:
    try:
        from dispatch.registry import update_treasury_balance
        update_treasury_balance("api_budget_usd", -float(cost_usd))
    except Exception:
        # Don't crash a chat call if registry write fails.
        pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ping", action="store_true", help="1-token request to verify auth")
    p.add_argument("--model", default="haiku-4.5")
    p.add_argument("--system", default="You are concise.")
    p.add_argument("--user", default="Reply with exactly: ok")
    args = p.parse_args()

    if args.ping:
        try:
            res = chat(args.model, args.system, args.user, max_tokens=4, track_cost=False)
            print(f"✓ openrouter ok | model={resolve_model(args.model)} | cost=${res['cost_usd']:.6f}")
            print(f"  reply: {res['text'].strip()[:80]}")
            return 0
        except Exception as e:
            print(f"✗ openrouter FAILED: {e}", file=sys.stderr)
            return 1
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
