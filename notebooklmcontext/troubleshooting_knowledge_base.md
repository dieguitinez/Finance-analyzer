# Nivo FX: Troubleshooting Knowledge Base & Lessons Learned

This document records recurring issues, non-obvious failure modes, and technical debt "gotchas" discovered during development and deployment on the Linux server.

## 🐍 Python & Libraries

### OANDA v20 Library: Response Handling
- **Issue**: Calls to `response.get("field", default)` can crash with `expected status [], got 200 (OK)` if the default value is not a status code.
- **Context**: The `v20` library overrides `dict.get()` behavior. The second argument refers to the **HTTP Status Code** expected, not a default value for the key.
- **Resolution**: Always pass `200` as the second argument if you are fetching a key from a successful response.
    - *Wrong*: `res.get("positions", [])`
    - *Correct*: `res.get("positions", 200)`
- **File affected**: `quantum_engine/nivo_tg_bot.py`

### yfinance on Headless Linux
- **Issue**: Data download fails for pairs like `EURUSD=X` on servers even when working locally.
- **Context**: Servers are often flagged by Yahoo's rate limiting or need a specific `yfinance` version to handle the updated Yahoo API structure.
- **Resolution**: 
    1. Force `yfinance>=0.2.51`.
    2. Implement OANDA as the **primary** data source in `DataEngine` via `v20`, using Yahoo only as a last-resort fallback.

## 📡 Deployment & Synchronization

### Git Sync Blocking
- **Issue**: `git pull` fails on the server due to "local changes" or "untracked files".
- **Context**: The `deploy_to_linux.ps1` script pushes code, but if the bot or sentinel creates log files or caches on-the-fly, Git blocks the update.
- **Resolution**: Use a "Hard Reset" to sync production.
    - `git fetch origin`
    - `git reset --hard origin/main`

### Service Restarts
- **Issue**: Code is updated but the bot or dashboard doesn't reflect changes.
- **Context**: Python scripts running as `systemd` services stay in memory.
- **Resolution**: Always restart services after a pull.
    - `sudo systemctl restart nivo-dashboard.service`
    - `sudo systemctl restart nivo-bot.service`

## 🧠 Trading Logic & Brain

### The "Long Bias" (Symmetric Logic)
- **Issue**: The system was entering BUYS but ignoring SELL opportunities.
- **Context**: The Brain original logic analyzed strength from 0-100 but only had a trigger for >60. Since SELL signals naturally produce low scores (e.g., 30), they never triggered.
- **Resolution**: Implement **Symmetric Thresholds**.
    - **BUY**: Score > 60
    - **SELL**: Score < 40
- **File affected**: `src/nivo_trade_brain.py`

### 1GB RAM Bottlenecks
- **Issue**: `/status` command in Telegram crashed the bot or was extremely slow.
- **Context**: Looping through a 15-pair watchlist and fetching detailed metrics for each causes high latency and memory spikes.
- **Resolution**: **Scan First, Detail Later**. 
    - First, list open positions (one API call).
    - Then, fetch details *only* for symbols with open trades.
- **File affected**: `quantum_engine/nivo_tg_bot.py`

### 🌍 Fundamental Engine & Strategy Expansion

#### Pullback (Retrocesos) Strategy: Bidirectional Rigor
- **Logic**: Operates on "discount" prices within a strong trend, treating both Longs and Shorts with equal priority.
- **Criteria (Bullish/Long)**:
    - Trend: Price > EMA 200.
    - Correction: Price touches/crosses EMA 50 (Downwards).
    - Trigger: RSI < 45.
- **Criteria (Bearish/Short)**:
    - Trend: Price < EMA 200.
    - Correction: Price rallies to EMA 50 (Upwards).
    - Trigger: RSI > 55.
- **Messaging**: Uses "Strategic Re-entry / RECARGA" labels in logs to emphasize high-probability entry points in both directions.

#### MarketPulse Integration
- **Context**: Standard Yahoo RSS feeds can be noisy. MarketPulse (OANDA) provides higher-quality institutional commentary.
- **Lesson**: Kai FX is more accurate when combining both sources and analyzing at least 20 headlines to filter out volatility noise.
