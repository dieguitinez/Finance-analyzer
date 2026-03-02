import sys
import os
import time
from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.auto_execution import NivoAutoTrader
from src.data_engine import DataEngine
from src.notifications import NotificationManager

load_dotenv()

def run_forced_execution():
    print("\n--- NIVO FX: FORCED EXECUTION TEST ---")
    print("Testing OANDA V20 Stop Loss Mathematics...\n")
    
    api_key = os.getenv("OANDA_ACCESS_TOKEN")
    account_id = os.getenv("OANDA_ACCOUNT_ID")
    env = "practice" if "practice" in os.getenv("OANDA_BASE_URL", "practice") else "live"

    if not api_key or not account_id:
        print("ERROR: Missing OANDA credentials in .env")
        return

    trader = NivoAutoTrader(api_key, account_id, environment=env)
    engine = DataEngine()

    test_pair_oanda = "GBP_USD"
    test_pair_yahoo = "GBPUSD=X"
    units = 100  # Increased to 100 units for OANDA minimum safety

    try:
        print(f"1. Fetching current market data for {test_pair_yahoo}...")
        df = engine.fetch_data(test_pair_yahoo, "15m")
        current_price = df['Close'].iloc[-1]
        
        # Calculate ATR and SL using the exact math from nivo_trade_brain.py & vm_executor.py
        atr_value = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean()
        
        # Base Stop Loss (1.5 ATR for Longs)
        base_sl_price = current_price - (atr_value * 1.5)
        
        # Protective Buffer (0.5 ATR away)
        execution_buffer = atr_value * 0.5
        final_sl_price = base_sl_price - execution_buffer
        
        # Trailing Stop distance (1.5 ATR originally)
        ts_distance = atr_value * 1.5

        print(f"2. Mathematical Generation:")
        print(f"   -> Current Price: {current_price:.5f}")
        print(f"   -> Calculated SL: {final_sl_price:.5f}")
        print(f"   -> Trailing Dist: {ts_distance:.5f}")
        
        print("\n3. Dispatching BUY via NivoAutoTrader (Check [DEBUG] lines below)...")
        response = trader.execute_trade(
            instrument=test_pair_oanda,
            units=units,
            stop_loss_price=final_sl_price,
            trailing_stop_distance=ts_distance
        )
        
        print("\n--- FINAL OANDA RESPONSE ---")
        if response.get("status") == "success":
            order_id = response.get('order_id')
            print(f"SUCCESS! OANDA accepted the payload.")
            print(f"Transaction ID: {order_id}")
            
            # Send Telegram Confirmation for forced test
            tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
            tg_chat = os.getenv("TELEGRAM_CHAT_ID")
            if tg_token and tg_chat:
                print("Sending Telegram confirmation...")
                NotificationManager.trade_execution_report(
                    pair=test_pair_oanda.replace("_", "/"),
                    action="BUY",
                    units=units,
                    order_id=order_id,
                    token=tg_token,
                    chat_id=tg_chat
                )
        else:
            print(f"REJECTED: {response.get('message')}")
        print("--- TEST COMPLETED ---")

    except Exception as e:
        print(f"Test Execution Failed: {str(e)}")

if __name__ == "__main__":
    run_forced_execution()
