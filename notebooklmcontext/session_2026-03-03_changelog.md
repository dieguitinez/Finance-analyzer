# Nivo FX & Stock Sentinel Changelog: March 3, 2026

## 🎯 Primary Focus: Interactivity & Time Precision

This session synchronized the Stock Sentinel with the user's interactive requirements and enforced strict institutional trading hours across all engines.

### 1. 🤖 New: Stock Sentinel Interactive Bot (`stock_tg_bot.py`)
- **Interactive Listener**: Created a new Telegram bot dedicated to Stocks (Token: `STOCK_TELEGRAM_BOT_TOKEN`).
- **Commands**:
  - `/ayuda` / `/help`: Interactive command guidance.
  - `/status`: Real-time view of 15 monitored tickers and open Alpaca positions.
  - `/saldo`: Live view of Alpaca Equity, Buying Power, and Daily PnL.
  - `/watchlist`: Lists the active AI stock watchlist.
- **Service**: Prepared `nivo-stock-bot.service` for 24/7 background operation on Linux.

### 2. ⏰ Strict Trading Hours (The "9:30 AM Rule" - Stocks Only)
- **Stock Sentinel**: Added `is_market_open()` check to `stock_watcher.py`.
- **Logic**: The Stock engine now remains in "Passive Watch Mode" until 9:30 AM (NY/Server time), preventing premature or low-liquidity entries in the equity market. **Forex remains 24/5.**

### 3. 📊 New: FX Trade Analyzer (`trade_analyzer.py`)
- **Intel Tool**: Created a performance analysis engine for the OANDA bot.
- **Metrics**: Calculates Win Rate, Total PnL (USD), and identifies the most traded instruments.
- **Lessons Learned**: Generates an AI-ready textual report summarizing performance and strategic advice for the user.

### 4. 🛠️ Infrastructure & Maintenance
- **Systemd**: Added configuration for the second Nivo Bot.
- **Log Sanitation**: Ensured new bots use structured logging to avoid disk saturation on the HP ENVY server.

---

## 🦾 Next Steps (Deployment)
1. Run `.\deploy_to_linux.ps1` to upload newest interactive modules.
2. Enable and start the new service: `sudo systemctl enable --now nivo-stock-bot.service`.
3. Restart FX and Stock Sentinels: `sudo systemctl restart nivo-sentinel.service stock-sentinel.service`.
