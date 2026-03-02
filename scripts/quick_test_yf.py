import yfinance as yf
import pandas as pd

def quick_test():
    symbol = "NZDUSD=X"
    print(f"--- Quick Yahoo Finance Test for {symbol} ---")
    try:
        df = yf.download(tickers=symbol, interval="1h", period="1d", progress=False)
        if df is not None and not df.empty:
            print(f"✅ SUCCESS: Data fetched for {symbol}")
            print(df.tail(1))
        else:
            print(f"❌ FAILED: No data for {symbol}")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    quick_test()
