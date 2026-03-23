import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv('ai_stock_sentinel/.env')

api_key = os.getenv("ALPACA_API_KEY")
api_secret = os.getenv("ALPACA_SECRET_KEY")
base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

print(f"Key: {api_key[:5] if api_key else 'None'}...")
print(f"Secret: {'Loaded' if api_secret else 'None'}")
print(f"URL: {base_url}")

client = TradingClient(api_key, api_secret, paper=("paper" in base_url))
account = client.get_account()

print(f"Status: {account.status}")
print(f"Daytrade count: {account.daytrade_count}")
print(f"Is Pattern Day Trader: {account.pattern_day_trader}")
print(f"Account properties:")
for attr in dir(account):
    if not attr.startswith("_"):
        val = getattr(account, attr)
        if not callable(val):
            print(f"  {attr}: {val}")
