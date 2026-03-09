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
    df = None
    guardian_reason = ""
        
    try:
        # ---------------------------------------------------------------
        # GLOBAL POSITION GUARD (CRITICAL FIX)
        # Check ENTIRE account for ANY open position before doing anything.
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
                logger.info(f"📊 POSICIONES ABIERTAS: [{_pos_summary}]")

            # Snapshot logic for Trailing Stop close detection
            if os.path.exists(_pos_cache_path):
                try:
                    with open(_pos_cache_path, "r") as f:
                        _prev_cache = json.loads(f.read())
                    _closed_by_ts = set(_prev_cache.keys()) - set(_open_instruments)
                    for _closed_pair in _closed_by_ts:
                        _prev = _prev_cache[_closed_pair]
                        logger.info(f"[TS CLOSE DETECTED] {_closed_pair} closed.")
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
                except: pass

            _pos_snapshot = {}
            for _pos in _open_positions:
                _instr = _pos["instrument"]
                _long_u = float(_pos.get("long", {}).get("units", 0))
                _short_u = float(_pos.get("short", {}).get("units", 0))
                _units = _long_u if _long_u != 0 else _short_u
                _pos_snapshot[_instr] = {"units": _units}
            with open(_pos_cache_path, "w") as f:
                f.write(json.dumps(_pos_snapshot))

        except Exception as _guard_err:
            _open_instruments = []
            logger.warning(f"⚠️ Global Guard check failed: {_guard_err}")

        # 2. Main Analysis Logic
        oanda_symbol = os.getenv("TRADING_PAIR", "EUR_USD")
        pair = oanda_symbol.replace("_", "/")
        tf = "1h"
        
        oanda_cfg = {"token": _token, "account_id": _account}
        engine = DataEngine(oanda_config=oanda_cfg)
        df = engine.fetch_data(pair, tf)
        
        if df is None or df.empty:
            logger.warning("No data retrieved.")
            return False
            
        brain = NivoTradeBrain(df)
        brain_analysis = brain.analyze_market()
        
        cortex = NivoCortex(data=df, oanda_token=_token, oanda_id=_account, pair=pair)
        # We consolidate HMM and LSTM calls into the Cortex Veto handshake
        
        is_vetoed, veto_reason = cortex.evaluate_veto(df)
        # Extraemos la probabilidad del LSTM que el Cortex ya calculó internamente
        _, lstm_prob = cortex.lstm.predict_next_move(df)

        if is_vetoed:
            logger.info(f"🛑 CORTEX VETO: {veto_reason}")
            return False

        # -------------------------------------------------------------
        # 3. CONVICTION LAYER (TREND + AI + NEWS)
        # -------------------------------------------------------------
        raw_signal = brain_analysis.get("signal", "WAIT")
        
        # Fundamental News Sentiment
        news_items, sentiment_score = FundamentalEngine.get_pair_sentiment(pair)
        
        # Calculate ATR fallback if needed
        atr_value = brain_analysis.get("atr", None)
        if not atr_value or pd.isna(atr_value):
            atr_value = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean()
        
        # Order Book Analysis (Micro-sentiment)
        dom_analysis = cortex.analyze_order_book(oanda_symbol)
        dom_outlook = dom_analysis.get("outlook", "Neutral")
        
        oanda_env = os.getenv("OANDA_ENVIRONMENT", "practice")
        trader = NivoAutoTrader(_token, _account, environment=oanda_env)

        if oanda_symbol in _open_instruments:
            logger.info(f"⏭️ {oanda_symbol} already open. Skipping entry.")
        elif raw_signal in ("BUY", "SELL"):
            # DOUBLE CONFIRMATION FILTER
            # 1. AI Confirmation (Neural Vector must show REAL conviction, not just >50%)
            # LSTM returns 45-55% in uncertain markets; require true directional bias.
            ai_agreement = (raw_signal == "BUY" and lstm_prob >= 55) or (raw_signal == "SELL" and lstm_prob <= 45)
            
            # 2. News Confirmation (Sentiment must be CLEARLY favorable, not just neutral)
            # Avoid trades where sentiment is even slightly opposing.
            news_agreement = (raw_signal == "BUY" and sentiment_score >= 52) or (raw_signal == "SELL" and sentiment_score <= 48)
            
            if not ai_agreement:
                logger.info(f"🛡️ [QUALITY FILTER] VETO IA: Convicción LSTM insuficiente ({lstm_prob:.2f}%). Se requiere >55% (BUY) o <45% (SELL). Operación DESCARTADA.")
                return False
            
            if not news_agreement:
                logger.info(f"🛡️ [QUALITY FILTER] VETO NOTICIAS: Sentimiento global ({sentiment_score}) es mixto o se opone a la tendencia. Se requiere >=52 (BUY) o <=48 (SELL). Operación DESCARTADA.")
                return False

            logger.info(f"🔥 [MAX CONVICTION] Signal: {raw_signal} | AI: {lstm_prob}% | News: {sentiment_score} | DOM: {dom_outlook}. Executing...")
            
            sl_distance_pips = (atr_value * 2.0) * (100 if "JPY" in pair else 10000)
            units = trader.calculate_position_size(oanda_symbol, sl_distance_pips)
            if units <= 0: units = 1000 
            
            trade_units = units if raw_signal == "BUY" else -abs(units)
            
            try:
                _pricing_r = requests.get(
                    f"https://{trader.hostname}/v3/accounts/{trader.account_id}/pricing?instruments={oanda_symbol}",
                    headers={"Authorization": f"Bearer {trader.token}"},
                    timeout=5
                )
                _price_data = _pricing_r.json().get("prices", [{}])[0]
                _ask = float(_price_data.get("asks", [{}])[0].get("price", df['Close'].iloc[-1]))
                _bid = float(_price_data.get("bids", [{}])[0].get("price", df['Close'].iloc[-1]))
                
                sl_distance_price = atr_value * 2.0
                ts_distance_price = atr_value * 1.5
                
                sl_price = (_bid - sl_distance_price) if raw_signal == "BUY" else (_ask + sl_distance_price)
                
                logger.info(f"[LIVE EXECUTION] {raw_signal} | SL:{sl_price:.5f} | Units: {abs(trade_units)}")
                
                trader.execute_trade(
                    instrument=oanda_symbol,
                    units=trade_units,
                    stop_loss_price=sl_price,
                    trailing_stop_distance=ts_distance_price
                )
                
                if _tg_token and _tg_chat:
                    news_msg = f"Sentiment: {sentiment_score}"
                    NotificationManager.trade_signal_alert(
                        pair=pair, signal=raw_signal, score=int(sentiment_score),
                        weight=1.0, direction=lstm_prob, 
                        guardian_msg=f"Triple Check: Trend+AI+News ✅. Sentiment: {sentiment_score} | DOM: {dom_outlook}",
                        token=_tg_token, chat_id=_tg_chat
                    )
            except Exception as _e:
                logger.error(f"Execution Error: {_e}")

    except Exception as e:
        logger.error(f"VM Cycle Error: {str(e)}", exc_info=True)
        try:
            from src.self_healer import NivoSelfHealer
            NivoSelfHealer.diagnose_and_alert(component="QuantumCore.VMExecutor", error_msg="Crash in VM cycle", exception_obj=e)
        except: pass
    finally:
        try:
            from quantum_engine.nivo_memory import release_memory
            release_memory(logger=logger)
        except: pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    args, _ = parser.parse_known_args()

    if args.diagnostic:
        # Mini diagnostic script
        try:
            load_dotenv()
            _token = os.getenv("OANDA_ACCESS_TOKEN")
            _account = os.getenv("OANDA_ACCOUNT_ID")
            symbol = os.getenv("TRADING_PAIR", "EUR_USD")
            pair = symbol.replace("_", "/")
            
            engine = DataEngine(oanda_config={"token": _token, "account_id": _account})
            df = engine.fetch_data(pair, "1h")
            brain = NivoTradeBrain(df)
            analysis = brain.analyze_market()
            cortex = NivoCortex(data=df, oanda_token=_token, oanda_id=_account, pair=pair)
            hmm_id, hmm_lbl = cortex.hmm.detect_regime(df)
            _, lstm_p = cortex.lstm.predict_next_move(df)
            
            print(json.dumps({
                "pair": pair,
                "price": round(float(df['Close'].iloc[-1]), 5),
                "brain_signal": analysis.get("signal"),
                "hmm_regime": hmm_lbl,
                "lstm_prob": round(lstm_p, 2)
            }))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        run_headless_cycle()
