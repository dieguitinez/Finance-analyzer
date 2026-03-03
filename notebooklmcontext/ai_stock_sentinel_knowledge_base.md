# Nivo AI Stock Sentinel: Project Knowledge Base

This document summarizes the technical architecture, intelligence logic, and deployment strategy for the AI Stock Sentinel integration.

## 🏛️ Hybrid Architecture
- **Dashboard:** Streamlit Community Cloud (Public access).
- **Execution Engine:** Local Linux Mint Server (Ryzen 5, 8GB RAM).
- **Bridge:** GitHub Actions & `deploy_to_linux.ps1` (SCP/SSH based deployment).
- **Data:** Alpaca API (Stock data/Trading) & OANDA API (Forex context).

## 🧠 Intelligence & Signal Logic
### Whale Detector (Institutional Footprint)
- **Logic:** Identifies volume spikes > 2.5x the rolling average.
- **Goal:** Detect institutional "smart money" entering the market before major moves.
- **Ref:** `ai_stock_sentinel/cerebral_engine.py`

### Sector Conviction (ASML Leading Indicator)
- **Logic:** Monitors ASML (Lithography monopoly) as a canary for the semiconductor sector.
- **Goal:** Bullish ASML signals increase conviction for other AI-related tickers (NVDA, TSM, etc.).
- **Ref:** `ai_stock_sentinel/stock_watcher.py`

## 🛡️ System & Reliability
### Systemd Integration
- **Service Name:** `stock-sentinel.service`
- **Location:** `/etc/systemd/system/stock-sentinel.service`
- **Behavior:** `Restart=always`, logs directed to systemd journal.
- **Monitoring Command:** `journalctl -u stock-sentinel.service -f`

### Log Management (Resource Protection)
- **Rotation:** `RotatingFileHandler` implemented in `stock_watcher.py`.
- **Limits:** Max 5MB per file, 5 backups preserved.
- **Cleanup:** Integrated into `scripts/clean_logs.sh`.

## 🌐 Dashboard Features
- **Account Intelligence:** Displays Live Alpaca Equity, Buying Power, and Daily PnL.
- **15 AI Monopolies Monitor:** Real-time pricing and "Vigilando" status for NVDA, TSM, ASML, ARM, AVGO, MU, AMD, SNPS, CDNS, LRCX, AMAT, KLAC, VRT, MRVL, SMCI.
- **Bilingual Glossary:** Integrated definitions for all 15 stocks and institutional terms in English/Spanish.

## 🛠️ Key Files
- `ai_stock_sentinel/stock_watcher.py`: Main execution loop.
- `ai_stock_sentinel/cerebral_engine.py`: AI filters and Whale Detector.
- `app.py`: Streamlit dashboard and UI logic.
- `stock-sentinel.service`: Linux systemd configuration.
- `deploy_to_linux.ps1`: Automated deployment pipeline.
