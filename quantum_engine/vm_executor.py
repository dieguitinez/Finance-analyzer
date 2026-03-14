import os
import time
import requests
import json
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd
import numpy as np
import sys
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import Nivo suite components
from src.data_engine import DataEngine, FundamentalEngine
from src.notifications import NotificationManager
from src.utils import is_market_open
from src.auto_execution import NivoAutoTrader
from src.nivo_trade_brain import NivoTradeBrain
from src.nivo_cortex import NivoCortex

# --- SETUP PERSISTENT LOGGING V4 ---
_log_dir = os.path.join(_project_root, "logs")
if not os.path.exists(_log_dir):
    os.makedirs(_log_dir, exist_ok=True)

_log_file = os.path.join(_log_dir, "nivo_fx.log")
_handler = RotatingFileHandler(_log_file, maxBytes=5*1024*1024, backupCount=7)
_formatter = logging.Formatter('%(asctime)s | NIVO EXECUTOR: [%(levelname)s] | %(message)s')
_handler.setFormatter(_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
# Add stream handler for real-time visibility
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_formatter)
logger.addHandler(_stream_handler)

def record_decision(pair, signal, hmm_regime, lstm_prob, sentiment, dom, order_id="N/A", reason=""):
    """
    Appends a bot decision to the persistent Trade Ledger.
    """
    import csv
    _ledger_path = os.path.join(_log_dir, "trade_ledger.csv")
    _file_exists = os.path.exists(_ledger_path)
    
    try:
        with open(_ledger_path, "a", newline="") as f:
            _writer = csv.writer(f)
            if not _file_exists:
                _writer.writerow(["Timestamp", "Pair", "Signal", "HMM_Regime", "LSTM_Prob", "Sentiment", "DOM", "Order_ID", "Reason"])
            _writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                pair, signal, hmm_regime, f"{float(lstm_prob):.2f}", 
                sentiment, dom, order_id, reason
            ])
    except Exception as e:
        logger.error(f"Failed to record in ledger: {e}")

def run_headless_cycle(pairs_list: list = None):
    """
    Main Loop for the Quant V4 Hybrid Strategy.
    Orchestrates Technicals, HMM Regimes, LSTM Probability, and News Sentiment.
    """
    if not is_market_open():
        logger.warning("Mercado Cerrado (Fin de Semana). Ejecución abortada por seguridad.")
        return False
        
    load_dotenv()
    
    if pairs_list is None:
        target_env = os.getenv("TRADING_PAIR", "EUR_USD")
        pairs_list = [p.strip() for p in target_env.split(",") if p.strip()]

    if not pairs_list:
        logger.warning("No se especificaron pares. Ciclo abortado.")
        return False

    logger.info(f"Iniciando ciclo de computación cuántica para: {', '.join(pairs_list)}")
    
    panic_lock_path = os.path.join(_project_root, ".panic_lock")
    if os.path.exists(panic_lock_path):
        logger.warning("🚨 [KILL SWITCH] .panic_lock detectado. Abortando ejecución.")
        return False

    # Check for global environment once
    _token = os.getenv("OANDA_ACCESS_TOKEN", "")
    _account = os.getenv("OANDA_ACCOUNT_ID", "")
    _base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    _tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    _tg_chat  = os.getenv("TELEGRAM_CHAT_ID", "")

    for oanda_symbol in pairs_list:
        pair = oanda_symbol.replace("_", "/")
        logger.info(f"\n--- Procesando Par: {pair} ---")
        
        try:
            # Check open positions once per iteration
            _temp_dir = os.path.join(_project_root, "temp")
            if not os.path.exists(_temp_dir): os.makedirs(_temp_dir, exist_ok=True)
            _pos_cache_path = os.path.join(_temp_dir, "nivo_open_positions.json")
        
            _r = requests.get(
                f"{_base_url}/v3/accounts/{_account}/openPositions",
                headers={"Authorization": f"Bearer {_token}"},
                timeout=5
            )
            _open_positions = _r.json().get("positions", [])
            _open_instruments = [p["instrument"] for p in _open_positions]
            
            # 2. Main Analysis Logic
            tf = "1h"
            engine = DataEngine(oanda_config={"token": _token, "account_id": _account})
            df = engine.fetch_data(pair, tf)
            
            if df is None or df.empty:
                logger.warning(f"Sin datos para {pair}.")
                continue
                
            brain = NivoTradeBrain(df)
            brain_analysis = brain.analyze_market()
            cortex = NivoCortex(data=df, oanda_token=_token, oanda_id=_account, pair=pair)
            
            hmm_id, hmm_lbl = cortex.hmm.detect_regime(df)
            _, lstm_prob = cortex.lstm.predict_next_move(df)
            is_vetoed, veto_reason = cortex.evaluate_veto(df)

            if is_vetoed:
                logger.info(f"🛑 CORTEX VETO para {pair}: {veto_reason}")
                record_decision(pair, "WAIT", hmm_lbl, lstm_prob, 0, "N/A", reason=f"VETO: {veto_reason}")
                continue

            raw_signal = brain_analysis.get("signal", "WAIT")
            _, sentiment_score = FundamentalEngine.get_pair_sentiment(pair)
            
            # Cache for Telegram Report
            try:
                report_data = {
                    "pair": pair,
                    "price": round(float(df['Close'].iloc[-1]), 5),
                    "brain_signal": raw_signal,
                    "hmm_regime": hmm_lbl,
                    "lstm_prob": round(float(lstm_prob), 2),
                    "gemini_sentiment": sentiment_score,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(os.path.join(_temp_dir, f"nivo_report_cache_{oanda_symbol}.json"), "w") as f:
                    json.dump(report_data, f)
            except: pass

            atr_value = brain_analysis.get("atr", None)
            if not atr_value or pd.isna(atr_value):
                atr_value = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean()
            
            dom_analysis = cortex.analyze_order_book(oanda_symbol)
            dom_outlook = dom_analysis.get("outlook", "Neutral")
            
            trader = NivoAutoTrader(_token, _account, environment="practice" if "practice" in _base_url else "live")

            if oanda_symbol in _open_instruments:
                logger.info(f"⏭️ {oanda_symbol} ya abierta. Saltando.")
            elif raw_signal in ("BUY", "SELL"):
                # HYBRID FINAL SAFETY LAYER
                ai_agreement = (raw_signal == "BUY" and lstm_prob >= 55) or (raw_signal == "SELL" and lstm_prob <= 45)
                news_agreement = (raw_signal == "BUY" and sentiment_score >= 52) or (raw_signal == "SELL" and sentiment_score <= 48)

                if not (ai_agreement and news_agreement):
                    logger.info(f"🛡️ [HYBRID VETO] IA:{ai_agreement} | NEWS:{news_agreement}. Señal abortada para {pair}.")
                    record_decision(pair, "WAIT", hmm_lbl, lstm_prob, sentiment_score, dom_outlook, reason="Veto Híbrido")
                    continue

                logger.info(f"🔥 [HYBRID CONVICTION] {pair} Ejecutando entrada...")
                try:
                    sl_dist = (atr_value * 2.0) * (100 if "JPY" in pair else 10000)
                    units = trader.calculate_position_size(oanda_symbol, sl_dist)
                    trade_units = units if raw_signal == "BUY" else -abs(units)
                    sl_price = (float(df['Close'].iloc[-1]) - (atr_value * 2.0)) if raw_signal == "BUY" else (float(df['Close'].iloc[-1]) + (atr_value * 2.0))
                    
                    trader.execute_trade(instrument=oanda_symbol, units=trade_units, stop_loss_price=sl_price, trailing_stop_distance=atr_value * 1.5)
                    
                    if _tg_token and _tg_chat:
                        NotificationManager.trade_signal_alert(pair=pair, signal=raw_signal, score=int(sentiment_score), weight=1.0, direction=lstm_prob, 
                                                               guardian_msg=f"Trend+AI+News ✅. DOM:{dom_outlook}", token=_tg_token, chat_id=_tg_chat)
                    
                    record_decision(pair, raw_signal, hmm_lbl, lstm_prob, sentiment_score, dom_outlook, order_id=getattr(trader, 'last_order_id', "EXECUTED"))
                except Exception as ex:
                    logger.error(f"Error en ejecución para {pair}: {ex}")

        except Exception as e:
            logger.error(f"Error en ciclo VM para {pair}: {str(e)}", exc_info=True)

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
        try:
            load_dotenv()
            _t = os.getenv("OANDA_ACCESS_TOKEN")
            _a = os.getenv("OANDA_ACCOUNT_ID")
            s = os.getenv("TRADING_PAIR", "EUR_USD")
            p = s.replace("_", "/")
            e = DataEngine(oanda_config={"token": _t, "account_id": _a})
            d = e.fetch_data(p, "1h")
            br = NivoTradeBrain(d)
            an = br.analyze_market()
            cx = NivoCortex(data=d, oanda_token=_t, oanda_id=_a, pair=p)
            hi, hl = cx.hmm.detect_regime(d)
            _, lp = cx.lstm.predict_next_move(d)
            _, fs = FundamentalEngine.get_pair_sentiment(p)
            print(json.dumps({
                "pair": p, "price": round(float(d['Close'].iloc[-1]), 5), "signal": an.get("signal"),
                "hmm": hl, "lstm": round(float(lp), 2), "news": fs
            }))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        run_headless_cycle()
