# sentinel.py
import os
import time
import requests
import logging
from dotenv import load_dotenv
import yfinance as yf

from src.nivo_trade_brain import NivoTradeBrain
from src.nivo_cortex import NivoCortex

# Establish robust OS-level console logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NIVO SENTINEL | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Security Implementation: Read internal API nodes
load_dotenv()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

def fetch_data_headless(ticker: str):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        return df
    except Exception as e:
        logger.error(f"Network fragmentation during data fetch: {e}")
        return None

def dispatch_n8n_webhook(payload: dict):
    if not N8N_WEBHOOK_URL:
        logger.error("SYSTEM HALT: N8N_WEBHOOK_URL is missing from .env security file.")
        return
       
    try:
        response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ High-Probability Trade Webhook successfully routed to n8n.")
    except Exception as e:
        logger.error(f"Failed to dispatch N8N webhook: {e}")

def run_infinite_sentinel():
    logger.info("Booting Nivo Headless Sentinel Daemon...")
    brain = NivoTradeBrain()
    cortex = NivoCortex()
   
    watch_assets = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"]
   
    while True:
        logger.info("--- Initiating 15-Minute Sweeping Cycle ---")
       
        for asset in watch_assets:
            df = fetch_data_headless(asset)
            if df is None or df.empty:
                continue
               
            score, signal = brain.analyze_market(df)
            veto, reason = cortex.evaluate_veto(df)
           
            # Actionable Execution Check
            if signal != "WAIT" and not veto and score >= 75:
                logger.warning(f"🚀 OPPORTUNITY DETECTED: {asset} | {signal} | SCORE: {score}")
               
                payload = {
                    "asset": asset,
                    "signal": signal,
                    "score": score,
                    "cortex_insight": reason,
                    "current_price": float(df['Close'].iloc[-1])
                }
                dispatch_n8n_webhook(payload)
            else:
                logger.info(f"[{asset}] Cleared. Result: {signal} (Score: {score} | Veto: {veto})")
               
        logger.info("Cycle complete. Going to sleep for 900 seconds (15m)...")
        time.sleep(900)

if __name__ == "__main__":
    run_infinite_sentinel()
