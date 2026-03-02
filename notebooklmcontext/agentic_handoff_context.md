# Nivo FX 3.0: Quantum & Execution Engine Context Handoff
Date: March 1, 2026

## 🎯 Executive Summary
This document serves as the absolute "Ground Truth" for any future AI Agent interacting with the **Nivo FX Trading System**. It documents the critical fixes applied during Phase 28, 29, and 30, specifically resolving fatal execution errors with the OANDA V20 API, introducing the "Nivo Nexus" 5-step analysis workflow, and mathematically defining Risk-Management constraints.

## 🛠️ Critical Bug Fixes: OANDA Execution Integrity
During live testing, the bot generated mathematically valid entry signals but failed to execute on OANDA, throwing `NoneType` and `STOP_LOSS_ON_FILL_LOSS` errors. 

### 1. The "Ghost Fill" Error (201 Created but Cancelled)
**Symptom:** The script expected an `orderFillTransaction` ID upon receiving a 201 HTTP status code from OANDA.
**Root Cause:** OANDA often accepts orders (201) but immediately cancels them server-side if margin or price rules are violated. The `v20.response.Response` object throws silent Python Exceptions if you attempt to access a non-existent `orderFillTransaction` dictionary key.
**The Fix (`src/auto_execution.py`):** The code was refactored to use `hasattr(response, "orderFillTransaction")` to safely parse the response and extract the exact `reason` from the `orderCancelTransaction` object.

### 2. The Stop Loss Rejection (`STOP_LOSS_ON_FILL_LOSS`)
**Symptom:** OANDA rejected orders due to invalid Stop Loss / Trailing Stop parameters.
**The Fixes (Three-fold):**
1.  **JPY Precision Rules:** OANDA completely rejects Payload parameters containing more than **3 decimals** for JPY pairs (e.g., `USD_JPY`, `EUR_JPY`, `CHF_JPY`). All other pairs require **5 decimals**. `auto_execution.py` now dynamically detects `"JPY" in instrument` and formats strings perfectly (`:.3f` vs `:.5f`).
2.  **Spread Volatility Buffer:** Stop losses initially calculated mathematically from ATR were sometimes placed exactly within OANDA's variable Bid/Ask spread, causing immediate rejection. `vm_executor.py` now adds an explicit **0.5x ATR Safety Buffer** to the absolute distance, pushing the Stop Loss into a guaranteed "safe zone" outside the spread.
3.  **Trailing Stop Conflict:** OANDA mathematically rejects any order where the `TrailingStopLoss` distance is exactly equal to or larger than the exact pip distance to the absolute `StopLoss`. The core logic initially set them both to `1.5x ATR`. To solve this, `auto_execution.py` now forces the Trailing Stop to be exactly **0.6x the distance** of the absolute Stop Loss.

## 🧠 The Nivo Nexus: 5-Step Intelligence Protocol
We have implemented a highly transparent workflow visible on the Streamlit Community Cloud frontend under the "Intelligence Protocol" tab, fully bilingual.
*   **Paso 1: Análisis Estructural (Simons)** - Hidden Markov Models detect the macro-regime. *[CÁLCULO CUÁNTICO ACTIVO]*
*   **Paso 2: Filtro Lineal** - EMA 50/200, RSI, Bollinger Bands confirm the baseline momentum.
*   **Paso 3: Gravedad Fundamental** - VADER NLP sentiment parsing of real-time Forex news sets the structural bias.
*   **Paso 4: Fase de Reflexividad (Soros)** - The "Reflexivity Multiplier" (0.75x to 1.25x) amplifies or dampens the trade signal based on whether technicals and news sentiment are conspiring together or clashing. *[CÁLCULO CUÁNTICO ACTIVO]*
*   **Paso 5: Veto Profundo** - LSTM Network (The expert model) validates the signal density. *[CÁLCULO CUÁNTICO ACTIVO]*

## 📊 Monitored Assets & Execution Precision
For any future mathematical generation or scaling, these exact symbol formats must be used:

| Pair (Display) | OANDA Ticker | Category | Precision |
| :--- | :--- | :--- | :--- |
| **EUR/USD** | `EUR_USD` | Mayor | 5 Decimals |
| **GBP/USD** | `GBP_USD` | Mayor | 5 Decimals |
| **USD/JPY** | `USD_JPY` | Mayor | 3 Decimals |
| **AUD/USD** | `AUD_USD` | Mayor | 5 Decimals |
| **USD/CAD** | `USD_CAD` | Mayor | 5 Decimals |
| **XAU/USD** | `XAU_USD` | Commodity | 3 Decimals |
| **BTC/USD** | `BTC_USD` | Cripto | 5 Decimals (Mirror) |

---

## 📖 Glossary: Quantum 3.0 Concepts
- **Nivo Nexus Protocol**: The 5-step intelligence workflow: 1. Simons (Regime), 2. Linear (Technical), 3. Fundamental (VADER), 4. Soros (Reflexivity), 5. Veto (Deep Learning).
- **Soros Reflexivity Multiplier**: A dynamic coefficient (0.75x to 1.25x) that amplifies position size when sentiment (news) and technicals (price) are in synergy, or dampens it when they clash.
- **Stop Loss Safety Buffer**: An additional **0.5x ATR** distance added to the mathematical stop loss to push it outside of OANDA's variable spreads and prevent immediate rejection.
- **STOP_LOSS_ON_FILL_LOSS**: A specific OANDA V20 error caused by placing a stop loss too close to the current ask price or having incorrect decimal precision.
- **EMERGENCY_KILL_SWITCH**: A global `.env` variable that halts all trade dispatches to OANDA instantly if set to `True`.
- **Journal Vacuuming**: The automated Linux maintenance process (`journalctl --vacuum`) that prevents logs from exhausting disk space during 1-minute scanning cycles.
- **Force Push Sync**: The necessary protocol to update the Streamlit Cloud dashboard from a sandboxed local environment using `git push origin main --force`.

---

## 📁 Phase 32: Linux Disk Space & Maintenance
To prevent the Linux server from filling up during continuous 1-minute market scanning:
1.  **`scripts/clean_logs.sh`**: Vacuums journals (7d/500MB), clears `__pycache__`, and removes old deployment archives.
2.  **`scripts/setup_cron.sh`**: Schedules the cleanup every Sunday at 00:00.
3.  **Journal Limit**: A 500MB global limit was implemented via `journald.conf` with `SystemMaxUse=500M`.

## 🌐 Phase 33: Git Synchronization & Force Push
Because the Windows machine is sandboxed, direct `git push` often fails. 
- **The Fix**: The local files in `src/` and `quantum_engine/` are the **Ground Truth**.
- **The Command**: Use `git push origin main --force` to sync the local fixed OANDA logic with the Streamlit Cloud web dashboard.

## ⚠️ CRITICAL DEPLOYMENT SAFEGUARDS
1.  **NO `.venv` UPLOADS**: The virtual environment folder (`.venv`) exceeds 250MB and violates GitHub's 100MB file limit. It MUST be excluded via `.gitignore`.
2.  **Repo Weight**: The repository must stay under **1MB**. If a push fails with "Large files detected," do NOT use Git LFS. Instead, run `git rm -r --cached .venv` followed by a fresh commit.
3.  **Branch Name**: Always use `main`. If a push fails with `refspec main does not match any`, rename the current branch using `git branch -m main`.

## 🤖 Directives for the Next Agent
1.  **Do NOT touch the `round()` or mathematical precision variables in `auto_execution.py`.** The logic (`decimals = 3 if "JPY" in instrument else 5`) is mathematically perfect for OANDA V20.
2.  If the user asks to modify risk parameters, do it in `nivo_trade_brain.py` (e.g., changing SL from 1.5 ATR to 2.0 ATR), but NEVER modify the 0.5 ATR buffer in `vm_executor.py`.
3.  **Deployment Protocol**: Always use `.\deploy_to_linux.ps1` for the headless Ubuntu VM. Ensure `git push origin main` is successful before looking at the Streamlit web dashboard.
4.  **Zero-Heavy-Entry Policy**: If you add new files, ensure they are not binaries or library folders. Use `requirements.txt` for all dependencies.
