import os
import sys
from dotenv import load_dotenv

# Ensure project root is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data_engine import DataEngine

def verify_symbols():
    load_dotenv()
    watchlist = os.getenv("WATCHLIST", "").split(",")
    watchlist = [p.strip() for p in watchlist if p.strip()]
    
    if not watchlist:
        # Fallback to test pairs if watchlist is empty
        watchlist = ["EUR/USD", "NZD/USD", "EUR/JPY", "XAU/USD", "BTC/USD"]
    
    print(f"--- Yahoo Finance Symbol Mapping Verification ---")
    engine = DataEngine()
    
    for pair in watchlist:
        # Normalize OANDA style names to Nivo UI style for mapping
        nivo_pair = pair.replace("_", "/")
        yf_symbol = DataEngine.get_symbol_map(nivo_pair)
        print(f"Nivo Pair: {nivo_pair:10} -> Yahoo Symbol: {yf_symbol}")
        
    print(f"\n--- Testing Data Fetch for NZD/USD ---")
    df = engine.fetch_data("NZD/USD", "1h", period="5d")
    if df is not None and not df.empty:
        print(f"✅ NZD/USD Fetch Success! Rows: {len(df)}")
        print(df.tail(2))
    else:
        print(f"❌ NZD/USD Fetch Failed (Expected if mapping is still wrong or network issue)")

if __name__ == "__main__":
    verify_symbols()
