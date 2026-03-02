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
    # 0. Emergency Panic Button Check
    kill_switch = os.getenv("EMERGENCY_KILL_SWITCH", "False").lower() == "true"
    if kill_switch:
        logger.warning(f"🛑 [EMERGENCY KILL SWITCH ACTIVATED] 🛑 Dropping {action} order for {instrument}. Autotrading is completely halted.")
        return False
        
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
        logger.error(f"❌ Execution failed: {result.get('message')}")
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
        # Par configurable desde .env (por defecto EUR/USD)
        oanda_symbol = os.getenv("TRADING_PAIR", "EUR_USD")  # Formato OANDA: EUR_USD, GBP_USD, etc.
        pair = oanda_symbol.replace("_", "/")  # Para mostrar: EUR/USD
        tf = "1h"
        
        logger.info(f"Assembling structural matrix for {pair} ({tf})...")
        engine = DataEngine()
        df = engine.fetch_data(DataEngine.get_symbol_map(pair), tf)
        
        if df is None or df.empty:
            logger.warning("No data retrieved. Exiting array cycle.")
            sys.exit(0)
            
        # 2. Hybrid Brain Analysis (Technical + Quantum)
        logger.info("Initializing Technical Brain Analysis...")
        brain = NivoTradeBrain(df)
        brain_analysis = brain.analyze_market()
        
        # 3. Instantiate Quantum Mathematical Modules
        q_bridge = QuantumBridge()
        guardian = CapitalGuardian(max_daily_loss_pct=-2.0, max_position_size=2.0)
        
        legacy_tech = brain_analysis.get("score", 50.0)
        
        # 4. Fundamental Intelligence (News Sentiment)
        # Replacing 60.0 static placeholder with live pair-specific news analysis
        _, legacy_fund = FundamentalEngine.get_pair_sentiment(pair)
        
        # Array Phase
        logger.info("Engaging Quantum Bridge Tensors...")
        q_res = q_bridge.execute_pipeline(df)
        
        final_score = q_bridge.calculate_nivo_q_score(
            legacy_tech_score=legacy_tech,
            legacy_fund_score=legacy_fund,
            q_regime_state=q_res.get('regime_id', 0),
            q_forecast_delta=q_res.get('qlstm_bull_prob', 0.5) * 100,
            q_position_weight=q_res.get('optimal_position_size', 1.0)
        )
        
        # Retrieve SL and TS from technical brain, adding an execution buffer to prevent spread rejection
        base_sl_price = brain_analysis.get("stop_loss", df['Close'].iloc[-1] * 0.99)
        atr_value = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean() # Simple proxy if brain fails
        ts_distance = brain_analysis.get("atr", atr_value) * 1.5
        
        # Protective Buffer: Push SL an extra 0.5 ATR away to survive OANDA spread volatility
        execution_buffer = atr_value * 0.5
        is_long_signal = final_score > 50
        sl_price = base_sl_price - execution_buffer if is_long_signal else base_sl_price + execution_buffer
        
        # 4. Guardian Risk Sandbox Filtering
        current_pnl = 0.0 # TODO: In production, query the actual live OANDA Account PnL ratio
        raw_signal = "BUY" if final_score > 65.0 else "SELL" if final_score < 35.0 else "WAIT"
        
        final_signal, capped_weight, guardian_msg = guardian.evaluate_trade(
            raw_signal=raw_signal,
            q_position_weight=q_res.get('optimal_position_size', 1.0),
            current_daily_pnl_pct=current_pnl,
            lang="en"
        )
        
        logger.info(f"Quantum Phase Complete. Guardian Output: {guardian_msg}")
        logger.info(f"Bridge Decision >> Signal: {final_signal} | Q-Multiplier: {capped_weight:.2f}x | Final Score: {final_score:.2f}")

        # --- Alerta Telegram: SOLO si hay senal real (BUY o SELL) ---
        tg_token  = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tg_chat   = os.getenv("TELEGRAM_CHAT_ID", "")
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
        # 5. Strict Memory Management for 1GB Micro-VM
        # This MUST occur before the HTTPS Broker Dispatch request is initialized to free up local sockets.
        logger.info("Executing Aggressive Memory Flush...")
        if 'df' in locals(): del df
        if 'q_bridge' in locals(): del q_bridge
        if 'guardian' in locals(): del guardian
        if 'prices' in locals(): del prices
        
        # Hard system ram flush
        gc.collect()
        logger.info("VM Memory Buffer Cleared successfully.")

    # 6. Broker Connection Route (Executes AFTER math overhead drops out of RAM)
    if "HOLD" not in final_signal and "CANCEL" not in final_signal and final_signal != "WAIT":
        logger.info("Initiating Live Broker HTTPS Dispatch Protocol (Safe Route)...")
        # 10,000 unit baseline proxy 
        trade_units = int(10000 * capped_weight)
        
        execute_oanda_safe_trade(
            instrument=oanda_symbol, 
            units=trade_units, 
            action=final_signal,
            stop_loss=sl_price,
            trailing_stop=ts_distance
        )
    else:
        logger.info("Metrics do not align for Live routing. Session Closed.")

if __name__ == "__main__":
    run_headless_cycle()
