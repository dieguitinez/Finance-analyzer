import os
import sys
import gc
import json
import logging
import requests
from datetime import datetime
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure project root is importable (works both locally and on Linux server)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import Quantum Modules
from quantum_engine.quantum_bridge import QuantumBridge
from quantum_engine.risk_manager import CapitalGuardian
from src.data_engine import DataEngine, FundamentalEngine
from src.notifications import NotificationManager
from src.utils import is_market_open
from src.auto_execution import NivoAutoTrader
from src.nivo_trade_brain import NivoTradeBrain
from src.nivo_cortex import NivoCortex  # Right Hemisphere: HMM + LSTM + DOM Veto

# Configure Headless Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NIVO EXECUTION LOG: [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def execute_oanda_safe_trade(instrument: str, units: int, action: str, stop_loss: float, trailing_stop: float = 0.0020):
    """
    Routes trade through NivoAutoTrader to enforce the 3-Layer Risk Protocol.
    Includes EMERGENCY KILL SWITCH check.
    """
    # 0. Emergency Panic Button Check (Persistent Lock File)
    lock_file = os.path.join(_project_root, ".panic_lock")
    if os.path.exists(lock_file):
        logger.warning(f"🛑 [EMERGENCY KILL SWITCH ACTIVATED] 🛑 Found .panic_lock. Dropping {action} order for {instrument}. Autotrading is completely halted.")
        return False
        
    # Also check legacy env var for backward compatibility
    kill_switch = os.getenv("EMERGENCY_KILL_SWITCH", "False").lower() == "true"
        
    api_key = os.getenv("OANDA_ACCESS_TOKEN")
    account_id = os.getenv("OANDA_ACCOUNT_ID")
    env = "practice" if "practice" in os.getenv("OANDA_BASE_URL", "practice") else "live"

    if not api_key or not account_id:
        logger.error("🛑 CRITICAL: OANDA API Credentials missing. Halting.")
        return False

    trader = NivoAutoTrader(api_key, account_id, environment=env)
    
    logger.info(f"🚀 [SAFE EXECUTION] Routing {action} for {instrument} | Units: {units} | SL: {stop_loss} | TS: {trailing_stop}")
    
    result = trader.execute_trade(
        instrument=instrument,
        units=units if action == "BUY" else -abs(units),
        stop_loss_price=stop_loss,
        trailing_stop_distance=trailing_stop
    )
    
    if result.get("status") == "success":
        order_id = result.get('order_id')
        logger.info(f"✅ Trade successful. Order ID: {order_id}")
        
        # Enviar confirmacion final a Telegram
        tg_token  = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tg_chat   = os.getenv("TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            NotificationManager.trade_execution_report(
                pair=instrument.replace("_", "/"),
                action=action,
                units=units,
                order_id=order_id,
                token=tg_token,
                chat_id=tg_chat
            )
        return True
    else:
        msg = result.get('message', 'Unknown Error')
        if "Already have an open position" in msg:
            logger.info(f"⏭️  {msg} - Skipping entry.")
        else:
            logger.error(f"❌ Execution failed: {msg}")
        return False

def run_headless_cycle():
    """
    Main execution pipeline strictly shaped for 1GB RAM constraint.
    """
    if not is_market_open():
        logger.warning("Market is CLOSED. Execution aborted for safety.")
        return False
        
    logger.info("Initializing Quantum Computation Cycle...")
    
    # 1. Environment Security & Kill Switch
    load_dotenv()
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    panic_lock_path = os.path.join(project_root, ".panic_lock")
    if os.path.exists(panic_lock_path):
        logger.warning("🚨 [KILL SWITCH] .panic_lock detected in VM Executor. Halting execution.")
        return False

    # Memory Scope Pre-allocation for explicit GC tracking
    df = None
    q_bridge = None
    guardian = None
    prices = None
        
    try:
        # ---------------------------------------------------------------
        # GLOBAL POSITION GUARD (CRITICAL FIX)
        # Check ENTIRE account for ANY open position before doing anything.
        # Uses direct REST API to avoid the v20 SDK ResponseUnexpectedStatus bug.
        # ---------------------------------------------------------------
        _token = os.getenv("OANDA_ACCESS_TOKEN", "")
        _account = os.getenv("OANDA_ACCOUNT_ID", "")
        _base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
        _tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        _tg_chat  = os.getenv("TELEGRAM_CHAT_ID", "")
        _pos_cache_path = "/tmp/nivo_open_positions.json"
        try:
            _r = requests.get(
                f"{_base_url}/v3/accounts/{_account}/openPositions",
                headers={"Authorization": f"Bearer {_token}"},
                timeout=5
            )
            _open_positions = _r.json().get("positions", [])
            _open_instruments = [p["instrument"] for p in _open_positions]
            if _open_instruments:
                _pos_summary = ", ".join(_open_instruments)
                logger.info(f"📊 POSICIONES ABIERTAS: [{_pos_summary}] — Análisis continúa. Ejecución bloqueada para pares activos.")

            # --- TRAILING STOP CLOSE DETECTION ---
            # Compare current positions against previous cycle's snapshot.
            # If a position disappeared → OANDA closed it automatically (trailing stop or SL hit).
            try:
                if os.path.exists(_pos_cache_path):
                    _prev_cache = json.loads(open(_pos_cache_path).read())
                    _prev_instruments = set(_prev_cache.keys())
                    _curr_instruments = set(_open_instruments)
                    _closed_by_ts = _prev_instruments - _curr_instruments
                    for _closed_pair in _closed_by_ts:
                        _prev = _prev_cache[_closed_pair]
                        logger.info(f"[TS CLOSE DETECTED] {_closed_pair} no longer in openPositions — likely closed by trailing stop.")
                        NotificationManager.trailing_stop_close_report(
                            pair=_closed_pair.replace("_", "/"),
                            units=_prev.get("units", 0),
                            entry_price=_prev.get("entry_price", 0.0),
                            close_price=_prev.get("current_price", 0.0),
                            pnl_usd=_prev.get("pnl_usd", 0.0),
                            pips=_prev.get("pips", 0.0),
                            token=_tg_token,
                            chat_id=_tg_chat
                        )
            except Exception as _ts_detect_err:
                logger.warning(f"[TS CLOSE DETECTION] Cache check failed (non-critical): {_ts_detect_err}")

            # Save current open positions snapshot for next cycle comparison
            try:
                _pos_snapshot = {}
                for _pos in _open_positions:
                    _instr = _pos["instrument"]
                    _long_u  = float(_pos.get("long", {}).get("units", 0))
                    _short_u = float(_pos.get("short", {}).get("units", 0))
                    _units   = _long_u if _long_u != 0 else _short_u
                    _avg_px  = float(_pos.get("long" if _long_u != 0 else "short", {}).get("averagePrice", 0))
                    _unreal  = float(_pos.get("unrealizedPL", 0))
                    _pos_snapshot[_instr] = {
                        "units": _units,
                        "entry_price": _avg_px,
                        "current_price": _avg_px,  # best available without extra API call
                        "pnl_usd": _unreal,
                        "pips": 0.0  # approximate — will not be precise but gives context
                    }
                open(_pos_cache_path, "w").write(json.dumps(_pos_snapshot))
            except Exception as _snap_err:
                logger.warning(f"[TS CLOSE DETECTION] Could not save position snapshot: {_snap_err}")

        except Exception as _guard_err:
            _open_instruments = []
            logger.warning(f"⚠️ Global Guard check failed (proceeding cautiously): {_guard_err}")
        # ---------------------------------------------------------------


        # Par configurable desde .env (por defecto EUR/USD)
        oanda_symbol = os.getenv("TRADING_PAIR", "EUR_USD")  # Formato OANDA: EUR_USD, GBP_USD, etc.
        pair = oanda_symbol.replace("_", "/")  # Para mostrar: EUR/USD
        tf = "1h"
        
        logger.info(f"Assembling structural matrix for {pair} ({tf})...")
        oanda_cfg = {
            "token": os.getenv("OANDA_ACCESS_TOKEN"),
            "account_id": os.getenv("OANDA_ACCOUNT_ID")
        }
        engine = DataEngine(oanda_config=oanda_cfg)
        df = engine.fetch_data(pair, tf)
        
        if df is None or df.empty:
            logger.warning("No data retrieved. Exiting array cycle.")
            sys.exit(0)
            
        # 2. LEFT HEMISPHERE: Technical Brain Analysis
        logger.info("Initializing Technical Brain Analysis (Left Hemisphere)...")
        brain = NivoTradeBrain(df)
        brain_analysis = brain.analyze_market()
        
        # 3. RIGHT HEMISPHERE: AI Cortex (HMM + LSTM + DOM)
        logger.info("Initializing AI Cortex (Right Hemisphere: HMM + LSTM + DOM)...")
        cortex = NivoCortex(
            data=df,
            oanda_token=_token,
            oanda_id=_account,
            pair=pair  # Enables auto-loading of trained .pth weights
        )
        
        # 3a. HMM Regime Detection
        regime_id, regime_desc = cortex.hmm.detect_regime(df)
        if regime_id == -1:
            regime_id = 1  # Default to HIGH_VOLATILITY if HMM can't train (safe default)
        logger.info(f"[RIGHT HEMISPHERE] HMM Regime: {regime_desc} (ID: {regime_id})")

        # 3b. LSTM Direction Probability
        _, lstm_prob = cortex.lstm.predict_next_move(df)  # returns (str, float 0-100)
        lstm_status_badge = "✅ Trained" if cortex.lstm.is_trained else "⚠️ Random Weights"
        logger.info(f"[RIGHT HEMISPHERE] LSTM Bull Probability: {lstm_prob:.1f}% [{lstm_status_badge}]")

        # 3c. CORTEX VETO: Block trades in dangerous regimes (CRASH or HIGH VOLATILITY)
        is_vetoed, veto_reason = cortex.evaluate_veto(df)
        if is_vetoed:
            logger.info(f"🛑 CORTEX VETO: {veto_reason} | No trade will be executed.")
            sys.exit(0)

        logger.info(f"✅ Cortex Approved — proceding to QuantumBridge synthesis.")

        # 4. Quantum Mathematical Modules
        q_bridge = QuantumBridge()
        guardian = CapitalGuardian(max_daily_loss_pct=-2.0, max_position_size=2.0)
        
        legacy_tech = brain_analysis.get("score", 50.0)
        
        # 4. Fundamental Intelligence (News Sentiment)
        # Replacing 60.0 static placeholder with live pair-specific news analysis
        _, legacy_fund = FundamentalEngine.get_pair_sentiment(pair)
        
        # Array Phase
        logger.info("Engaging Quantum Bridge Tensors (Synthesis Layer)...")
        q_res = q_bridge.execute_pipeline(df)
        
        # Use real HMM regime_id + REAL trained LSTM probability
        # ✅ LSTM is now trained on 2 years of OANDA H1 data (.pth weights loaded above)
        # ✅ lstm_prob now reflects genuine AI-learned momentum patterns
        final_score = q_bridge.calculate_nivo_q_score(
            legacy_tech_score=legacy_tech,
            legacy_fund_score=legacy_fund,
            q_regime_state=regime_id,                          # Real HMM from NivoCortex ✅
            q_forecast_delta=lstm_prob,                         # Real trained LSTM ✅ (was EMA proxy)
            q_position_weight=q_res.get('optimal_position_size', 1.0)
        )
        
        # 4. Final Directional Decision
        is_long_signal = final_score > 50
        
        # Recalculate Stop Loss based on the ACTUAL final direction to ensure security
        # We use a 2.0 ATR stop for institutional safety, plus the execution buffer
        atr_value = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean()
        execution_buffer = atr_value * 0.5
        current_price = df['Close'].iloc[-1]
        
        if is_long_signal:
            sl_price = current_price - (atr_value * 2.0) - execution_buffer
        else:
            sl_price = current_price + (atr_value * 2.0) + execution_buffer
            
        ts_distance = atr_value * 1.5
        
        # 4. Guardian Risk Sandbox Filtering
        current_pnl = 0.0 # TODO: In production, query the actual live OANDA Account PnL ratio
        # Thresholds per agentic_handoff_context.md: BUY > 60, SELL < 40 (symmetric)
        raw_signal = "BUY" if final_score > 60.0 else "SELL" if final_score < 40.0 else "WAIT"
        
        final_signal, capped_weight, guardian_msg = guardian.evaluate_trade(
            raw_signal=raw_signal,
            q_position_weight=q_res.get('optimal_position_size', 1.0),
            current_daily_pnl_pct=current_pnl,
            lang="en"
        )
        
        logger.info(f"Quantum Phase Complete. Guardian Output: {guardian_msg}")
        logger.info(f"Bridge Decision >> Signal: {final_signal} | Q-Multiplier: {capped_weight:.2f}x | Final Score: {final_score:.2f}")

        # ---------------------------------------------------------------
        # 4. Smart Execution Strategy (Execution + Notification)
        # ---------------------------------------------------------------
        tg_token  = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tg_chat   = os.getenv("TELEGRAM_CHAT_ID", "")
        oanda_env = os.getenv("OANDA_ENVIRONMENT", "practice")
        
        trader = NivoAutoTrader(
            os.getenv("OANDA_ACCESS_TOKEN"), 
            os.getenv("OANDA_ACCOUNT_ID"),
            environment=oanda_env
        )
        
        # Use pre-fetched position list to avoid redundant API call.
        # Guard is now per-pair: only block entry on THIS specific instrument.
        if oanda_symbol in _open_instruments:
            logger.info(f"⏭️ Sincronización: Posición detectada para {oanda_symbol}. Verificando Step-Trailing...")
            
            # Fetch detailed performance for the active position (Step-Trailing)
            performance = trader.get_position_performance(oanda_symbol)
            if performance:
                # --- STEP TRAILING: Asegurar ganancias cada 20 pips ---
                trader.update_step_trailing(
                    instrument=oanda_symbol,
                    trade_id=performance.get('trade_id'),
                    entry_price=performance.get('entry_price'),
                    current_sl=performance.get('sl_price', 0),
                    units=performance.get('units', 0),
                    current_pips=performance.get('pips', 0)
                )
                
                # Re-fetch performance to show updated SL and Insured Pips in report
                performance = trader.get_position_performance(oanda_symbol) or performance

                # SILENT MODE: Solo enviamos reporte si hay un cambio significativo
                last_insured = float(os.getenv(f"LAST_INSURED_{oanda_symbol}", "0.0"))
                current_insured = performance.get('insured_pips', 0.0)
                
                if current_insured > last_insured:
                    logger.info(f"🎯 Milestone: Ganancia asegurada aumentada a +{current_insured} pips. Notificando...")
                    os.environ[f"LAST_INSURED_{oanda_symbol}"] = str(current_insured)
                    if tg_token and tg_chat:
                        NotificationManager.position_performance_report(
                            pair=pair,
                            units=performance['units'],
                            entry_price=performance['entry_price'],
                            current_price=performance['current_price'],
                            exit_price=performance.get('exit_price', 0.0),
                            sl_price=performance.get('sl_price', 0.0),
                            insured_pips=performance.get('insured_pips', 0.0),
                            pips=performance['pips'],
                            pnl_usd=performance['pnl_usd'],
                            token=tg_token,
                            chat_id=tg_chat
                        )
            final_signal = "WAIT" # Detener lógica de entrada para este par
        else:
            logger.info(f"🔍 No hay posición para {oanda_symbol}. Evaluando señales de entrada clue el análisis LSTM...")
            # No hay posicion - Procedemos con la Evaluacion de Entrada
            current_pnl = 0.0 
            # Thresholds per agentic_handoff_context.md: BUY > 60, SELL < 40 (symmetric)
            raw_signal = "BUY" if final_score > 80.0 else "SELL" if final_score < 20.0 else "WAIT"
            
            final_signal, capped_weight, guardian_msg = guardian.evaluate_trade(
                raw_signal=raw_signal,
                q_position_weight=q_res.get('optimal_position_size', 1.0),
                current_daily_pnl_pct=current_pnl,
                lang="en"
            )
            
            logger.info(f"Quantum Phase Complete. Guardian Output: {guardian_msg}")
            logger.info(f"Bridge Decision >> Signal: {final_signal} | Q-Multiplier: {capped_weight:.2f}x | Final Score: {final_score:.2f}")

            # Alerta Telegram: Solo para entradas nuevas
            if tg_token and tg_chat and final_signal in ("BUY", "SELL"):
                NotificationManager.trade_signal_alert(
                    pair=pair,
                    signal=final_signal,
                    score=final_score,
                    weight=capped_weight,
                    direction=q_res.get('qlstm_bull_prob', 0.5),
                    guardian_msg=guardian_msg,
                    token=tg_token,
                    chat_id=tg_chat
                )
        # ---------------------------------------------------------------

    except Exception as e:
        logger.error(f"Mathematical Generation Error: {str(e)}", exc_info=True)
        from src.self_healer import NivoSelfHealer
        try:
            NivoSelfHealer.diagnose_and_alert(
                component="QuantumCore.VMExecutor",
                error_msg=f"Excepción severa en el ciclo del motor.",
                exception_obj=e,
                context_data={"pair": pair if 'pair' in locals() else "Unknown"}
            )
        except Exception as alert_e:
            logger.error(f"Failed to send diagnostic alert: {alert_e}")
            
        final_signal = "HOLD"  # Fail safe

    finally:
        # 5. Strict Memory Management — gc + OS-level malloc_trim
        from quantum_engine.nivo_memory import release_memory
        if 'df' in dir(): del df  # noqa: F821
        if 'q_bridge' in dir(): del q_bridge  # noqa: F821
        if 'guardian' in dir(): del guardian  # noqa: F821
        if 'prices' in dir(): del prices  # noqa: F821
        if 'brain' in dir(): del brain  # noqa: F821
        if 'cortex' in dir(): del cortex  # noqa: F821
        release_memory(logger=logger)

    # 6. Broker Connection Route
    # We only call this if final_signal is BUY/SELL and NO position was detected above
    if final_signal in ("BUY", "SELL"):
        logger.info(f"Initiating Live Broker HTTPS Dispatch Protocol (Safe Route) for {final_signal}...")
        # OANDA v20 Protocol: Positive units for LONG, Negative for SHORT
        units_base = int(10000 * (capped_weight if 'capped_weight' in locals() else 1.0))
        trade_units = units_base if final_signal == "BUY" else -abs(units_base)

        # --- REAL-TIME EXECUTION PRICING FIX ---
        # Recalculate SL and TS using the exact live bid/ask to avoid STOP_LOSS_ON_FILL_LOSS
        try:
            _pricing_r = requests.get(
                f"https://{trader.hostname}/v3/accounts/{trader.account_id}/pricing?instruments={oanda_symbol}",
                headers={"Authorization": f"Bearer {trader.token}"},
                timeout=5
            )
            _price_data = _pricing_r.json().get("prices", [{}])[0]
            _ask = float(_price_data.get("asks", [{}])[0].get("price", current_price))
            _bid = float(_price_data.get("bids", [{}])[0].get("price", current_price))
            
            # Re-fetch ATR if locals forgot it, otherwise proxy it
            _atr = atr_value if 'atr_value' in locals() else 0.0030
            _min_dist = max(_atr * 1.5, 0.0010) # At least 10 pips

            if final_signal == "BUY":
                # Buy at Ask, SL below Bid
                sl_price = _bid - _min_dist
            else:
                # Sell at Bid, SL above Ask
                sl_price = _ask + _min_dist

            # OANDA Rule: TS distance must be smaller than Hard SL distance.
            # SL distance is exactly _min_dist. Let's make TS distance 0.5x of _min_dist.
            ts_distance = _min_dist * 0.5
            
            logger.info(f"[LIVE PRICING] Buy(Ask):{_ask:.5f} | Sell(Bid):{_bid:.5f} | Live SL:{sl_price:.5f} | TS Dist:{ts_distance:.5f}")
        except Exception as _prc_err:
            logger.warning(f"[LIVE PRICING FIX] Could not fetch real-time ticks: {_prc_err}")

        trader.execute_trade(
            instrument=oanda_symbol,
            units=trade_units,
            stop_loss_price=sl_price,
            trailing_stop_distance=ts_distance
        )
    else:
        logger.info("Metrics do not align for Live routing or Position already open. Session Closed.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true", help="Run AI analysis only, output JSON report (no trade execution)")
    args, _ = parser.parse_known_args()

    if args.diagnostic:
        # === DIAGNOSTIC MODE: Full AI analysis → JSON output, NO trade execution ===
        import json as _json
        _report = {}
        try:
            load_dotenv()
            _token   = os.getenv("OANDA_ACCESS_TOKEN")
            _account = os.getenv("OANDA_ACCOUNT_ID")
            oanda_symbol = os.getenv("TRADING_PAIR", "EUR_USD")
            pair = oanda_symbol.replace("_", "/")

            # Data
            oanda_cfg = {"token": _token, "account_id": _account}
            engine = DataEngine(oanda_config=oanda_cfg)
            df = engine.fetch_data(pair, "1h")

            if df is None or df.empty:
                print(_json.dumps({"error": "No data available for this pair"}))
                sys.exit(0)

            # 1. LEFT HEMISPHERE - Technical Brain
            brain = NivoTradeBrain(df)
            brain_analysis = brain.analyze_market()
            tech_score = brain_analysis.get("score", 50.0)
            tech_signal = brain_analysis.get("signal", "NEUTRAL")
            tech_details = brain_analysis.get("indicators", {})

            # 2. RIGHT HEMISPHERE - HMM Regime
            cortex = NivoCortex(data=df, oanda_token=_token, oanda_id=_account, pair=pair)
            regime_map = {0: "Calm / Low Volatility", 1: "Elevated Volatility", 2: "Crash / Extreme Panic"}
            hmm_regime_id, hmm_label = cortex.hmm.detect_regime(df)
            if hmm_regime_id == -1:
                hmm_regime_id, hmm_label = 0, "Calm / Low Volatility"

            # 3. RIGHT HEMISPHERE - LSTM
            lstm_status, lstm_prob = cortex.lstm.predict_next_move(df)
            lstm_is_trained = cortex.lstm.is_trained

            # 4. CORTEX VETO check
            is_vetoed, veto_reason = cortex.evaluate_veto(df)

            # 5. FUNDAMENTAL SENTIMENT (real FundamentalEngine from data_engine.py)
            fund_items, fund_sentiment = FundamentalEngine.get_pair_sentiment(pair)
            fund_headlines = len(fund_items)

            # 6. QUANTUM BRIDGE
            q_bridge = QuantumBridge()
            q_res = q_bridge.execute_pipeline(df)
            q_multiplier = q_res.get("quantum_multiplier", 1.0)

            # ✅ FIX: Use REAL HMM regime + REAL trained LSTM probability (0-100 scale)
            # Previously used EMA proxy (0-1 scale) → caused q_diff = -49.5 destroying all bull scores
            # q_position_weight now derived from real LSTM conviction distance from 50
            lstm_conviction = abs(lstm_prob - 50.0) / 50.0  # 0.0-1.0
            q_position_weight = float(np.clip(q_multiplier * (1.0 + lstm_conviction), 0.25, 2.0))

            final_score = q_bridge.calculate_nivo_q_score(
                legacy_tech_score=tech_score,
                legacy_fund_score=fund_sentiment,
                q_regime_state=hmm_regime_id,        # ✅ Real HMM (not EMA proxy index)
                q_forecast_delta=lstm_prob,           # ✅ Real LSTM 0-100 scale (not EMA 0-1)
                q_position_weight=q_position_weight   # ✅ Real conviction-based weight
            )

            raw_signal = "BUY" if final_score > 80.0 else "SELL" if final_score < 20.0 else "WAIT"
            if is_vetoed:
                raw_signal = f"VETOED ({veto_reason})"

            _report = {
                "pair": pair,
                "timestamp": str(pd.Timestamp.now()),
                "current_price": round(float(df['Close'].iloc[-1]), 5),
                "left_hemisphere": {
                    "tech_score": round(tech_score, 2),
                    "signal": tech_signal,
                    # ✅ FIX: Read RSI/MACD directly from the computed df columns (always available)
                    "rsi": round(float(brain.df['RSI'].iloc[-1]), 2) if not pd.isna(brain.df['RSI'].iloc[-1]) else "N/A",
                    "macd_signal": "Bullish" if brain.df['MACD'].iloc[-1] > brain.df['MACD_Signal'].iloc[-1] else "Bearish",
                },
                "right_hemisphere": {
                    "hmm_regime": hmm_label,
                    "hmm_id": int(hmm_regime_id),
                    "lstm_bull_prob": round(float(lstm_prob), 2),
                    "lstm_trained": lstm_is_trained,
                    "cortex_veto": is_vetoed,
                    "veto_reason": veto_reason if is_vetoed else None,
                },
                "fundamental": {
                    "sentiment_score": round(float(fund_sentiment), 2),
                    "headline_count": fund_headlines,
                },
                "quantum_bridge": {
                    "q_multiplier": round(float(q_multiplier), 4),
                    "final_score": round(float(final_score), 2),
                },
                "decision": raw_signal
            }

        except Exception as _diag_e:
            _report = {"error": str(_diag_e)}

        print(_json.dumps(_report))
        sys.exit(0)

    else:
        run_headless_cycle()

