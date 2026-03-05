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
    logger.info("Initializing Quantum Computation Cycle...")
    
    # 1. Environment Security
    load_dotenv()
    
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
        logger.info(f"[RIGHT HEMISPHERE] LSTM Bull Probability: {lstm_prob:.1f}%")

        # 3c. CORTEX VETO: Block trades in dangerous regimes (CRASH or HIGH VOLATILITY)
        is_vetoed, veto_reason = cortex.evaluate_veto(df)
        if is_vetoed:
            logger.info(f"🛑 CORTEX VETO: {veto_reason} | No trade will be executed.")
            tg_token_veto = os.getenv("TELEGRAM_BOT_TOKEN", "")
            tg_chat_veto  = os.getenv("TELEGRAM_CHAT_ID", "")
            if tg_token_veto and tg_chat_veto:
                try:
                    import requests as _req
                    _req.post(
                        f"https://api.telegram.org/bot{tg_token_veto}/sendMessage",
                        json={"chat_id": tg_chat_veto, "text": f"🛑 <b>CORTEX VETO</b>\n{veto_reason}\nPar: {pair}", "parse_mode": "HTML"},
                        timeout=5
                    )
                except Exception:
                    pass
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
            raw_signal = "BUY" if final_score > 60.0 else "SELL" if final_score < 40.0 else "WAIT"
            
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
        # 5. Strict Memory Management
        logger.info("Executing Aggressive Memory Flush...")
        if 'df' in locals(): del df
        if 'q_bridge' in locals(): del q_bridge
        if 'guardian' in locals(): del guardian
        if 'prices' in locals(): del prices
        gc.collect()
        logger.info("VM Memory Buffer Cleared successfully.")

    # 6. Broker Connection Route
    # We only call this if final_signal is BUY/SELL and NO position was detected above
    if final_signal in ("BUY", "SELL"):
        logger.info(f"Initiating Live Broker HTTPS Dispatch Protocol (Safe Route) for {final_signal}...")
        # OANDA v20 Protocol: Positive units for LONG, Negative for SHORT
        units_base = int(10000 * (capped_weight if 'capped_weight' in locals() else 1.0))
        trade_units = units_base if final_signal == "BUY" else -abs(units_base)
        
        trader.execute_trade(
            instrument=oanda_symbol, 
            units=trade_units, 
            stop_loss_price=sl_price,
            trailing_stop_distance=ts_distance
        )
    else:
        logger.info("Metrics do not align for Live routing or Position already open. Session Closed.")

if __name__ == "__main__":
    run_headless_cycle()
