import os
import sys
from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.auto_execution import NivoAutoTrader
from src.data_engine import DataEngine

load_dotenv()

api_key = os.getenv("OANDA_ACCESS_TOKEN")
account_id = os.getenv("OANDA_ACCOUNT_ID")
env = "practice" if "practice" in os.getenv("OANDA_BASE_URL", "practice") else "live"

trader = NivoAutoTrader(api_key, account_id, environment=env)

# Try fetching current price for EUR_USD
engine = DataEngine()
df = engine.fetch_data("EUR_USD", "15m")
current_price = df['Close'].iloc[-1]
atr = df['High'].iloc[-14:].mean() - df['Low'].iloc[-14:].mean()

print(f"Current Price: {current_price:.5f} | ATR: {atr:.5f}")

# Test 1: Market Order (BUY) with no stops
print("Test 1: Market Order ONLY (NO STOPS)...")
# Note: execute_trade requires stop_loss_price. We will temporarily monkeypatch it or just send raw request
order_request = trader.ctx.order.market(
    trader.account_id,
    instrument="EUR_USD",
    units=10
)
if order_request.status == 201:
    print(f"Test 1 SUCCESS: {order_request.get('orderFillTransaction').id if hasattr(order_request, 'orderFillTransaction') else 'No Fill'}")
else:
    print(f"Test 1 FAILED: {order_request.get('errorMessage')}")

print("\n--- Test 2: Standard execution with SL ---")
# SL for BUY is BELOW current price
sl_price = current_price - (atr * 1.5)
ts_dist = atr * 1.5

print(f"Attempting BUY 10 units. SL: {sl_price:.5f} TS: {ts_dist:.5f}")
res = trader.execute_trade("EUR_USD", 10, sl_price, ts_dist)

print(f"Result: {res}")
