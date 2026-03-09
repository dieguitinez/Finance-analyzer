# Nivo System - Session Learnings & Fixes Context

**Date:** March 6, 2026 (Reflecting on March 5-6 operations)

This document serves as a persistent context file for future AI agents to understand recent bugs, architectural decisions, and the overall stability state of both the Nivo Forex Bot and the Nivo AI Stock Sentinel.

## 1. Remote Server & SSH Access Learnings

- **The Issue:** The Linux Server (192.168.1.240) had connection issues causing agents to get "stuck".
- **The Fix:** We configured the local Windows `~/.ssh/config` to use Agent Forwarding (`ForwardAgent yes`) and pre-shared keys. The previous agent successfully logged in and stored the SSH parameters.
- **Sudo Access:** We rely on the hardcoded password to execute `sudo` commands (e.g., via `echo "password" | sudo -S systemctl restart...`) because passwordless sudo could not be safely configured due to `/etc/sudoers` permission blocks.
- **Rule for Future Agents:** Always use `ssh diego@192.168.1.240` directly. The environment handles the keys.

## 2. Stock Bot (Alpaca) - Fractional Orders & Duplicate Buys Bug

- **The Issue:** On March 5th, the bot rapidly bought multiple fractional shares of the same tech stocks in the exact same second, violating the position limits and draining buying power.
- **The Root Cause:** Alpaca fractional Market Orders stay in a `pending/accepted` state for a few seconds before filling. The bot's loop checked `self.executor.has_open_position()`, which returned `False` because the order wasn't filled yet. Consequently, the bot sent the `BUY` command again and again.
- **The Fix:** We modified `stock_watcher.py` to strict-check: `if self.executor.has_open_position(symbol) or self.executor.has_pending_orders(symbol):`.
- **Learning:** *Never rely solely on open positions when dealing with fractional shares. Always query pending orders via the broker API before dispatching a new trade signal.*

## 3. Stock Bot - Python Logging Buffering (systemd)

- **The Issue:** `journalctl -u stock-watcher` was dumping logs in massive 10-minute blocks rather than streaming line by line. This made debugging the duplicate buy issue incredibly difficult because all timestamps appeared identical.
- **The Fix:** We injected `Environment=PYTHONUNBUFFERED=1` into `/etc/systemd/system/stock-watcher.service`.
- **Learning:** Python buffers `stdout` heavily when running under systemd. Always explicitly unbuffer it for trading bots where exact second-level timestamps are critical to trace race conditions.

## 4. Forex Bot (OANDA) - LSTM Scoring Bias (Sell Bias)

- **The Issue:** The Forex bot (Nivo Sentinel) was scanning the market perfectly but generating 0 trades. The Quantum Bridge logs showed constant `Wait` and `Sell` signals with scores stubbornly sitting in the ~35-45 range, despite neutral market conditions.
- **The Root Cause:** The Legacy technical/fundamental indicators output scores below 50 in low volatility. The LSTM (AI) correctly predicted neutral-to-bullish momentum (e.g. 51%), but its impact ratio was too weak (`0.3x`), allowing the old legacy filters to drag the total score bearish.
- **The Fix:** We boosted the `q_impact` multipliers in `quantum_engine/quantum_bridge.py` (`0.6x` for calm markets, `1.2x` for trending markets).
- **Learning:** When scaling outputs from 0 to 100 via differential math (Distance from 50), the Quantum layer (AI predictions) must have enough mathematical weight to override weak legacy indicators, otherwise the bot will suffer from perpetual vetoes or severe directional biases.

## 5. Stock Bot - Market Hours Sync

- **Confirmed behavior:** The Stock Bot halts operations implicitly on Fridays at 16:00 EST. It does NO live scanning over the weekend (Saturdays/Sundays). It wakes up Monday at 08:00 AM (for analysis) and begins executing live trades at 10:00 AM EST to avoid the "Morning Shakeout" volatility.

## Directives for Next Agent

1. **Context First:** Read this file before attempting to "fix" duplicate trades or logging issues on the server.
2. **Server Time:** The server runs on EST (New York Time).
3. **Bot Locations:**
   - Forex Bot: `/home/diego/nivo_fx/sentinel.py`
   - Stock Bot: `/home/diego/nivo_fx/ai_stock_sentinel/stock_watcher.py`
