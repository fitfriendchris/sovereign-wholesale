# Engine Archetype: Algorithmic Trading (Omni)

```yaml
engine_id: algo_trading
display_name: Algorithmic Trading
one_liner: Live algorithmic trading on MetaTrader 5 — Omni is the canonical instance.
```

## Project status
Omni is **already running and live** at MidasFX (1:1000 leverage, Magic 20250411).
Symbols: XAUUSD primary, XAGUSD secondary. Other broker-offered symbols allowed.

## Workdir + key paths
```
~/Omni-full-ALGO-Trading-Bot/
  python/                      # signal engine, executor, watchdog
  shared/signals.json          # latest signal payload
  shared/omni_data.json        # MT5 bridge data
  logs/                        # live + backtest logs
~/Library/Application Support/net.metaquotes.wine.metatrader5/...Common/Files/
                               # MT5 EA exports (D1/H4/H1/M30/M15/M5/M1 per symbol)
```

## Standard tactics
- Kill zones: London 07-10 UTC, NY 12-16 UTC
- 5% risk compound; TP1@2R(50%), TP2@4R(30%), TP3@6R(20%)
- ICT/SMC concepts: BOS, CHoCH, FVG, orderblock, liquidity sweeps
- All XAUUSD/XAGUSD symbols must be in MT5 Market Watch (run OmniSetup.mq5 if missing)

## Default Owner: Operations
Operations Manager owns Omni's health (uptime, EA status, account.ready, PnL).

## Hard rules (non-negotiable per Order Flow rule 10)
- **Omni risk parameters are read-only** to all Managers except Operations
- No agent pauses or restarts the Omni daemon without Operator confirmation
- Profits flow to Treasury for reporting/allocation, never direct redirection
- Engineering may not push code to Omni without Operator approval

## Common Manager dispatch patterns
```
sovereign /dispatch operations omni "verify EA account.ready=true and Market Watch has XAUUSD/XAGUSD"
sovereign /dispatch operations omni "tail watchdog.log for last 50 lines, summarize anomalies"
sovereign /dispatch engineering omni "review python/scaling_engine.py — TP1 partial close not closing 50%"
sovereign /dispatch treasury omni "calculate week-over-week PnL change"
```

## KPIs tracked
- Daily PnL (gross + net)
- Open positions count
- Drawdown from peak equity
- Win rate, average R:R
- Trades per kill zone

## Kill criteria (for portfolio review only — never auto-kill Omni)
- Drawdown > 30% (alert Operator immediately, recommend pause)
- 3+ consecutive losing weeks (Operator decision: tune or pause)
- EA disconnected from broker for >2h (Operator decision)
