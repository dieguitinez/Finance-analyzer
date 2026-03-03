# Session Changelog — 2026-02-27

## Changes Made This Session

### 1. Python Environment Rebuilt
- **Problem:** `.venv` used Python 3.14.3, incompatible with `hmmlearn` (needs C compiler)
- **Fix:** Installed Python 3.12.10 via `winget`, recreated `.venv`, installed all 16 deps
- **Status:** ✅ All packages working (`streamlit 1.54`, `torch 2.10`, `hmmlearn 0.3.3`)

### 2. RAM Optimization — `app.py`
- Added `import gc`
- `@st.cache_resource(max_entries=1)` on `load_models()`
- `@st.cache_data(max_entries=5)` on `fetch_market_data`, `fetch_news_data`, `fetch_seasonality_data`
- `gc.collect()` + `del brain, cortex` after AI analysis block
- `chat_history` capped at 50 messages (was unbounded)

### 3. RAM Optimization — `src/nivo_cortex.py`
- Added `import gc`
- All arrays use `np.float32` (halves memory vs float64)
- `gc.collect()` + explicit `del` at end of `evaluate_veto()`

### 4. Bug Fix — `quantum_engine/quantum_bridge.py`
- **Bug:** `app.py` line 244 called `QuantumBridge.execute_pipeline(data)` which didn't exist
- **Fix:** Added full `execute_pipeline()` method with float32 arrays, rolling volatility regime detection, EMA momentum scoring, gc.collect()
- Also added `_ema()` and `_default_result()` helper methods

### 5. Critical Fix — `src/nivo_cortex.py` (Complete Rewrite)
- **Bug:** app.py expected `NivoCortex(data, oanda_token=...)` with `.hmm`, `.lstm` sub-objects and methods `.detect_market_regime()`, `.predict_next_move()`, `.analyze_order_book()`. Old file had a completely different API. The Cortex was always silently failing (caught by try/except) — it was NEVER executing.
- **Fix:** Rewrote to 4 OOP classes:
  - `MarketRegimeDetector` — HMM (3 states: Low Vol, High Vol, Crash)
  - `NivoLSTM` + `CPUOptimizedLSTM` — PyTorch LSTM predictor
  - `OrderBookAnalyzer` — OANDA v20 order book microstructure
  - `NivoCortex` — Orchestrator with sub-objects `.hmm`, `.lstm`, `.order_book`
- **Status:** ✅ Verified — HMM running (regime detection active), LSTM active (0.5% Bearish forecast), DOM accessible

### 6. Created `.env` File
- Copied OANDA practice credentials from `secrets.toml` into `.env` format
- This enables `vm_executor.py` and `market_sentinel.py` to load credentials via `python-dotenv`
- Token: `18428416d...` | Account: `101-001-38641822-001`

### 7. Documentation Updated
- `notebooklmcontext/project_context.md` — Full project history (Phases 1-10)
- `notebooklmcontext/session_2026-02-27_changelog.md` — This file
