import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os

def analyze():
    # Load ledger
    ledger_path = "trade_ledger_remote.csv"
    if not os.path.exists(ledger_path):
        print(f"Error: {ledger_path} not found")
        return

    df = pd.read_csv(ledger_path)
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC') # Ensure UTC
    
    # Filter for strong LSTM conviction (even if vetoed)
    # We'll look for Prob > 53% (Long) or < 47% (Short)
    strong_signals = df[(df['LSTM_Prob'] > 53.0) | (df['LSTM_Prob'] < 47.0)].copy()
    
    if strong_signals.empty:
        print("No strong LSTM signals found in ledger.")
        return

    print(f"Found {len(strong_signals)} strong AI signals to verify.")
    
    # Group by pair to minimize yfinance calls
    results = []
    for pair in strong_signals['Pair'].unique():
        # Yahoo Finance ticker mapping
        ticker = pair.replace("/", "") + "=X"
        if pair == "USD/JPY": ticker = "JPY=X" # USD/JPY in YF is often JPY=X or USDJPY=X
        
        print(f"Processing {pair} ({ticker})...")
        
        pair_data = strong_signals[strong_signals['Pair'] == pair].sort_values('Timestamp')
        
        # Fetch historical data for the range
        start_date = pair_data['Timestamp'].min() - timedelta(days=1)
        end_date = pair_data['Timestamp'].max() + timedelta(days=2)
        
        try:
            hist = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval='1h')
            if hist.empty:
                print(f"No data found for {ticker}")
                continue
                
            for _, row in pair_data.iterrows():
                ts = row['Timestamp']
                prob = row['LSTM_Prob']
                direction = "LONG" if prob > 50 else "SHORT"
                
                # Find the closest price at timestamp
                # YF data is hourly, so we find the hour
                # Localize YF index to UTC for comparison
                hist.index = hist.index.tz_convert('UTC')
                idx = hist.index.get_indexer([ts], method='nearest')[0]
                entry_price = hist.iloc[idx]['Close']
                
                # Look 4h and 24h later
                try:
                    price_4h = hist.iloc[idx + 4]['Close']
                    pips_4h = (price_4h - entry_price) if direction == "LONG" else (entry_price - price_4h)
                    
                    # Convert to pips (approximate)
                    # For JPY, pips are usually at 2nd decimal. For others, 4th.
                    multiplier = 100 if "JPY" in pair else 10000
                    pips_4h_val = float(pips_4h * multiplier)
                    
                    results.append({
                        'Timestamp': ts,
                        'Pair': pair,
                        'Direction': direction,
                        'Prob': prob,
                        'Entry': float(entry_price),
                        'Pips_4h': pips_4h_val,
                        'Success': pips_4h_val > 0
                    })
                except IndexError:
                    continue
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    report_df = pd.DataFrame(results)
    if not report_df.empty:
        report_df.to_csv("missed_opportunities_report.csv", index=False)
        print("\n--- ANALYSIS COMPLETE ---")
        print(f"Total signals analyzed: {len(report_df)}")
        print(f"Win Rate (if executed): {report_df['Success'].mean():.2%}")
        print(f"Avg Pips (4h): {report_df['Pips_4h'].mean():.2f}")
        
        # Show top 5 missed trades
        print("\nTop 5 Missed Opportunities (Vetoed):")
        print(report_df.sort_values('Pips_4h', ascending=False).head(5))
    else:
        print("No matches found in market data.")

if __name__ == "__main__":
    analyze()
