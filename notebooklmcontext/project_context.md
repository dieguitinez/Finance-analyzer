# Nivo FX Intelligence Suite — Full Project Context

> **Last Updated:** 2026-02-28  
> **Purpose:** Onboard any future AI agent or developer to this project instantly.  
> **Owner:** Nivo Partners

---

## 1. What Is This Project?

A **Forex/Commodity/Crypto trading intelligence system** built with Python. It combines classical technical analysis with AI models (HMM, LSTM) and quantum-inspired mathematical pipelines to generate trading signals. Two execution modes:

1. **Dashboard Mode** — Full Streamlit web app (7 tabs, bilingual EN/ES)
2. **Headless Mode** — Math-only pipeline for 24/7 Linux server operation + automated OANDA trading

---

## 2. Architecture & File Map

```
Finance Analyzer/
├── app.py                          # Streamlit dashboard (main UI, ~620 lines)
├── requirements.txt                # Python 3.12 dependencies (16 packages)
├── .env.example                    # Template for OANDA + n8n credentials
├── .streamlit/
│   ├── secrets.toml                # API keys (OANDA, Gemini)
│   └── secrets_template.toml       # Template
│
├── src/                            # Core brain modules
│   ├── nivo_trade_brain.py         # Technical analysis (EMA, RSI, BB, MACD, ATR, ADX)
│   ├── nivo_cortex.py              # AI layer (HMM regime + LSTM prediction + DOM)
│   ├── data_engine.py              # Data fetcher (OANDA v20 primary, Yahoo fallback)
│   └── notifications.py            # Twilio/alert manager
│
├── quantum_engine/                 # Quantum-inspired pipeline
│   ├── quantum_bridge.py           # Merges classical + quantum scores, execute_pipeline()
│   ├── risk_manager.py             # CapitalGuardian (kill switch, position sizing)
│   ├── market_sentinel.py          # Lightweight watcher daemon (<20MB RAM)
│   ├── vm_executor.py              # Headless math pipeline + OANDA trade execution
│   ├── phase1_qpca.py              # Quantum PCA
│   ├── phase2_hqmm.py              # Hybrid Quantum Markov Model
│   ├── phase3_qlstm.py             # Quantum LSTM
│   ├── phase4_qaoa.py              # Quantum Approximate Optimization
│   └── test_oanda_auth.py          # OANDA credential test script
│
├── notebooklmcontext/              # Context docs for future agents
│
└── .agent/skills/                  # 70+ Antigravity agent skills
```

---

## 3. Evolution History (All Phases)

### Phase 1-3: Foundation (Initial Sessions)
- Created modular `src/` structure with `DataEngine` (OANDA v20 + Yahoo fallback)
- Built `NivoTradeBrain` — pure NumPy/Pandas technical analysis (EMA, RSI, BB, MACD, ATR, ADX)
- Integrated Gemini AI chat assistant ("Kai FX") in Streamlit
- Configured OANDA credentials in `.streamlit/secrets.toml`

### Phase 4: NivoCortex Refactoring
- Refactored monolithic cortex into **4 OOP classes**:
  - `MarketRegimeDetector` — HMM (3 states: Low Vol, High Vol, Crash)
  - `OrderBookAnalyzer` — OANDA order book microstructure
  - `NivoLSTM` — PyTorch LSTM predictor (60-candle lookback, 50 hidden units)
  - `NivoCortex` — Orchestrator wrapper with string enums

### Phase 5: Supervisor Handshake
- Two-column dashboard: **Brain** (technical) vs **Cortex** (AI)
- Decision Matrix combining both layers for final BUY/SELL/WAIT verdict
- Fallback logic when Cortex is offline

### Phase 6: Performance Optimization
- `@st.cache_resource` for models (load once)
- `@st.cache_data` with TTL (60s prices, 15min news, 24h seasonality)
- `concurrent.futures.ThreadPoolExecutor` for parallel data fetching
- Session state persistence to prevent tab-switching recalculation

### Phase 7: Gemini API Hardening
- Discovered available models via `genai.list_models()`
- Implemented **5-model cascade** (each with independent quota pool)
- Error handling prevents 429/404 from crashing the app

### Phase 8: Quantum Engine Integration
- Created `quantum_engine/` package with qPCA, HQMM, QLSTM, QAOA proxies
- `QuantumBridge` merges classical + quantum scores
- `CapitalGuardian` — kill switch with max daily loss limit (-2%)
- New tabs: "⚛️ Quantum Projections" and "🛡️ Risk Management"
- Bilingual support (EN/ES) throughout

### Phase 9: Linux Server Deployment (Initial Design)
- Created `systemd` service configs for `nivo-dashboard` and `nivo-sentinel`
- `market_sentinel.py` watches volatility, spawns `vm_executor.py` on events
- Built for 1GB RAM constraint environments

### Phase 10: RAM Optimization (2026-02-27)
- Reinstalled Python 3.12.10 (was 3.14, incompatible with hmmlearn)
- Added `max_entries` limits to all Streamlit caches
- Downcasted all arrays to `np.float32` (halves memory)
- Added `gc.collect()` after AI model inference
- Capped `chat_history` at 50 messages
- Fixed missing `QuantumBridge.execute_pipeline()` method
- Added bilingual Glossary tab (📖)

### Phase 11: Linux Production Deploy (2026-02-28) ✅ COMPLETED
- **Server:** `diego@192.168.1.240` (HP ENVY x360 Convertible, Linux Mint)
- **Deploy script:** `deploy_to_linux.ps1` — run from Windows PowerShell, packages and transfers project via SCP to `~/nivo_fx/`
- **Run command (Windows):** `.\.deploy_to_linux.ps1 -RemoteUser "diego" -RemoteIP "192.168.1.240"`
- **systemd services installed:** `nivo-dashboard.service` (port 8501) + `nivo-sentinel.service`
- **Dashboard URL:** `http://192.168.1.240:8501` (accessible from any device on LAN)
- **Venv path on Linux:** `/home/diego/nivo_fx/.venv/`
- **Status:** Active, running, auto-restarts on crash, starts on boot
- **Note:** First `pip install` may fail silently — fix with `pip install --upgrade pip && pip install -r requirements.txt`

### Phase 12: Telegram Notifications (PENDING — next session)
- Plan: Add `send_telegram_alert()` to `market_sentinel.py` using Telegram Bot API (free, uses `requests`)
- Triggers: BUY/SELL signal, Guardian block, sentinel restart
- No Twilio — Telegram Bot is 100% free
- User needs to: create bot via @BotFather → get TOKEN + chat_id → share with agent

### Phase 10: RAM Optimization (2026-02-27, Current Session)
- Reinstalled Python 3.12.10 (was 3.14, incompatible with hmmlearn)
- Added `max_entries` limits to all Streamlit caches
- Downcasted all arrays to `np.float32` (halves memory)
- Added `gc.collect()` after AI model inference
- Capped `chat_history` at 50 messages
- Fixed missing `QuantumBridge.execute_pipeline()` method
- Added bilingual Glossary tab (📖)

---

## 4. Signal Generation Pipeline

```
Data (OANDA/Yahoo) → NivoTradeBrain (Score 0-100) → NivoCortex (HMM Regime + LSTM Direction)
                                                          ↓
                                              QuantumBridge.execute_pipeline()
                                                          ↓
                                              CapitalGuardian (Kill Switch)
                                                          ↓
                                              FINAL DECISION: BUY / SELL / WAIT
```

### Decision Matrix
| Brain Signal | Cortex Regime | LSTM | Decision |
|---|---|---|---|
| BUY | LOW_VOL | UP | 🚀 EXECUTE LONG |
| SELL | LOW_VOL | DOWN | 📉 EXECUTE SHORT |
| Any | CRASH | Any | 🛑 BLOCKED |
| Any | HIGH_VOL | Any | ⚠️ CAUTION |
| WAIT | — | — | ⏳ NO TRADE |

---

## 5. Execution Modes

### Mode A: Dashboard (`streamlit run app.py`)
Full Streamlit UI with 7 tabs: Technical Analysis, Fundamental Intelligence, Seasonality, Kai FX Chat, Glossary, Quantum Projections, Risk Management.

### Mode B: Headless Math-Only (`python quantum_engine/vm_executor.py`)
Runs the full math pipeline WITHOUT Streamlit. Designed for:
- Linux server cron jobs or systemd timers
- 1GB RAM constraint environments
- Automated trade execution via OANDA API

### Mode C: Sentinel + Executor (Production)
`market_sentinel.py` (lightweight watcher, <20MB RAM) monitors volatility. When conditions trigger, it spawns `vm_executor.py` as a subprocess.

---

## 6. OANDA Practice Account Integration

Already implemented in `vm_executor.py`:

1. Copy `.env.example` → `.env`
2. Fill OANDA Practice credentials (`OANDA_ACCESS_TOKEN`, `OANDA_ACCOUNT_ID`)
3. Test: `python quantum_engine/test_oanda_auth.py`
4. Run: `python quantum_engine/vm_executor.py`

If signal is BUY/SELL and Guardian permits → executes FOK Market Order via REST API (10,000 units × quantum weight).

---

## 7. Tech Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit 1.54 |
| Data | OANDA v20 REST / Yahoo Finance |
| Technical Analysis | Pure NumPy/Pandas (no TA-Lib) |
| AI: Regime Detection | HMM (hmmlearn 0.3.3) |
| AI: Price Prediction | LSTM (PyTorch 2.10 CPU) |
| AI: Chat | Gemini 2.0 Flash (5-model cascade) |
| Risk Management | Custom CapitalGuardian |
| Broker | OANDA v20 REST API |
| Python | 3.12.10 |

## 8. Key Design Principles

- **No TA-Lib** — All indicators manually vectorized with NumPy
- **No GPU required** — LSTM designed for CPU inference (32 hidden units)
- **Float32 everywhere** — Trading doesn't need float64 precision
- **Sentinel/Executor split** — Sentinel <20MB RAM, executor spawned only on events
- **Bilingual (EN/ES)** — All UI text and Guardian messages
- **Model cascade** — Falls through 5 Gemini variants if quota exhausted
- **Aggressive GC** — `gc.collect()` + explicit `del` after every AI inference cycle
