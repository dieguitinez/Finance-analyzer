# 🤖 AGENT HANDOFF CONTEXT - DONCHIAN STABLE VERSION

**Date Saved:** March 9, 2026
**System:** Nivo FX Bot (Forex Trading)

### 📌 Purpose of this Backup

This folder (`backup_donchian_stable/`) contains a pristine, working backup of the Forex trading bot specifically configured for the **Donchian Breakout Trend-Following Strategy** with **Double Confirmation**. The user requested this backup to preserve the stable logic before experimenting with any "hybrid" approaches that might mix high-frequency scalping (from the legacy strategy) with this low-frequency trend approach.

### 🏗️ Architecture (HOW IT WORKS)

This system is designed for **Minimal RAM Footprint** and executes via Linux cron/timer rather than an infinite while-loop.

1. **`nivo-sentinel.timer` & `nivo-sentinel.service`**: Linux systemd timer that executes `quantum_engine/market_sentinel.py` exactly every 15 minutes.
2. **`market_sentinel.py`**: A very lightweight script (no pandas, just standard library requests). It checks OANDA for a >75 BPS price swing or checks if we currently have an open position. If yes, it wakes up the main executor.
3. **`vm_executor.py`**: The heavy engine. Runs only when called. It downloads market data, runs indicators, asks the AI (`nivo_cortex.py`) for a prediction, and asks the news sentiment logic for confirmation.
4. **`nivo-bot.service` (`nivo_tg_bot.py`)**: Runs 24/7. It listens to Telegram commands like `/panic` and creates a `.panic_lock` file to halt the `vm_executor` immediately if needed.
5. **`nivo-watchdog.service` (`nivo_watchdog.py`)**: Runs every 5 minutes to monitor RAM (alerts if >90%) and rotates logs if they exceed 100MB.

### 🛠️ Key Fixes Applied in this Version (DO NOT REVERT)

Future agents editing this codebase **must** be aware of the following bug fixes that are active in this backup:

* **Bug 1 (Double Confirmation was too weak):** In `vm_executor.py`, the AI agreement filter was boosted from `>50` to `>55` for Longs, and `<45` for Shorts. News sentiment was tightened to `>=52` and `<=48`. Do not go back to permissive 45-55 ranges, as it introduces false signals.
* **Bug 2 (Trailing Stop 0.0 PnL Bug):** In `vm_executor.py` `run_headless_cycle()`, the position cache used to only save `"units"`. This caused the Telegram trailing stop report to say `$0.00` profit. Now, the snapshot saves `entry_price` and `unrealizedPL`.
* **Bug 3 (Dummy RSI in Dashboard/Logs):** `nivo_trade_brain.py` used to have `self.df['RSI'] = 50` hardcoded. It now uses `import pandas_ta as ta` to calculate the real mathematical 14-period RSI.
* **Bug 4 (Silent Cycles):** Added a `logger.info("Cycle complete. No valid Trade Signal...")` at the bottom of `vm_executor.py` so the `nohup.out` doesn't look frozen on dead markets.

### ⚠️ Differences vs Legacy Strategy

In the parent directory, there is another folder called `backup_legacy_strategy`.

* **Legacy:** Used `auto_execution.py` attached to streaming WebSockets. It was aggressive, high-frequency, based on MACD reversions, and consumed significant RAM.
* **This Folder (Donchian):** Uses Linux Timers (`market_sentinel.py`), is patient, follows 50-period breakouts, and consumes almost zero RAM while sleeping.

### 📋 Instructions for Future Agents

If the user asks you to implement a "hybrid" strategy, **READ THIS FILE FIRST**. Compare the contents of `vm_executor.py` here against the `auto_execution.py` in the legacy folder. Ensure you do not accidentally overwrite the Kill Switch (`panic_lock`) logic or the PnL snapshot fixes when merging features.
