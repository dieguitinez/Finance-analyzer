# Nivo FX Changelog: March 2, 2026

## 🎯 Primary Focus: SDK Migration & Production Stability

This session focused on migrating from the deprecated `google-generativeai` to the new `google-genai` SDK and resolving critical data fetch issues affecting the Linux server (Nivo Sentinel).

### 1. 🚀 Gemini SDK Migration (google-genai)
- **Dependency**: Replaced `google-generativeai` with `google-genai` in `requirements.txt`.
- **Implementation**: Updated `app.py` and `src/self_healer.py` to use `genai.Client()`.
- **Resiliancy**: Implemented a **Model Cascade** in both the dashboard and the self-healer. This tries `gemini-2.0-flash` first, and if quota (429) or model errors occur, it automatically falls back to other Flash/Lite variants to maximize available free tier requests.

### 2. 📉 Yahoo Finance Data Fix
- **Issue**: `EURUSD=X` download failure on Linux server.
- **Root Cause**: Outdated `yfinance` version on the server.
- **Fix**: Pinned `yfinance>=0.2.51` in `requirements.txt` and verified data fetch logic.

### 3. 🏦 OANDA Live/Practice Integration
- **Fix**: Refactored `src/nivo_cortex.py` (`OrderBookAnalyzer`) to dynamically detect the account type.
- **Logic**: Now correctly targets `api-fxpractice.oanda.com` for demo/practice accounts and `api-fxtrade.oanda.com` for live accounts based on the provided account ID format.

### 4. 🧠 Self-Healer & AI Diagnostics
- **Bug**: AI diagnostics were failing with "Gemini API no configurada".
- **Fixes**:
    - Added missing `GOOGLE_API_KEY` to the `.env` file on the server.
    - Updated `src/self_healer.py` to check both `GOOGLE_API_KEY` and `GEMINI_API_KEY`.
    - Updated the default model to `gemini-2.0-flash`.

### 5. 🎨 Streamlit UI Polish
- **Deprecation**: Replaced `use_container_width=True` with `width='stretch'` in all `st.plotly_chart` calls to comply with Streamlit 1.40+.

## 🛠️ Deployment Summary
- **Git**: All changes pushed to `main` branch.
- **Remote Namespace Conflict Fixed**: Resolved `ImportError: cannot import name 'genai' from 'google'` on the server by performing a clean uninstall/reinstall of `google-genai` inside the `.venv`.
- **Remote Environment**: Verified that `yfinance` and `google-genai` are now functional in the production environment.
- **Services**: Updated and restarted `nivo-sentinel.service`.

### 6. 🦾 Nivo Trade Brain & Logic Optimization
- **Symmetric Thresholds**: Fixed "Long Bias" by implementing symmetric logic: BUY (> 60), SELL (< 40).
- **Fundamental Expansion**: Increased news limit to 20 headlines and integrated **MarketPulse (OANDA)** RSS feed into the `FundamentalEngine`.
- **Logic Alignment**: Ensured technical and fundamental scores use the same 0-100 normalization for the QuantumBridge.

### 7. 🤖 Telegram Command Center (v2.0)
- **New Commands**: Added `/entries`, `/scan`, `/balance`, `/dashboard`, and `/oanda`.
- **v20 Support**: Fixed a critical library error in the `/entries` command related to `response.get()` status codes.
- **Performance**: Optimized the `/status` command to only query active positions, significantly reducing latency and server load.
