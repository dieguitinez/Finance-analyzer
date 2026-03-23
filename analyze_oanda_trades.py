import os
import requests
import json
from datetime import datetime, timedelta

# Load OANDA credentials from .env
def load_env():
    env_path = r'c:\Users\qqqq\.gemini\antigravity\playground\Finance Analyzer\ai_forex_v4_institutional\.env'
    if not os.path.exists(env_path):
        print(f"Error: .env not found at {env_path}")
        return False
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                parts = line.strip().split('=', 1)
                if len(parts) == 2:
                    key, val = parts
                    os.environ[key] = val.strip('"').strip("'")
    return True

if not load_env():
    exit(1)

OANDA_ACCESS_TOKEN = os.environ.get("OANDA_ACCESS_TOKEN")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID")
OANDA_ENVIRONMENT = os.environ.get("OANDA_ENVIRONMENT", "practice")
OANDA_BASE_URL = os.environ.get("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")

headers = {
    "Authorization": f"Bearer {OANDA_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def get_account_summary():
    url = f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/summary"
    response = requests.get(url, headers=headers)
    return response.json()

def get_open_positions():
    url = f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/positions"
    response = requests.get(url, headers=headers)
    return response.json()

def get_closed_trades():
    # Fetch more trades
    url = f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/trades?state=CLOSED&count=50"
    response = requests.get(url, headers=headers)
    return response.json()

def main():
    print("--- OANDA ACCOUNT DIAGNOSTIC ---")
    summary = get_account_summary()
    if 'account' in summary:
        acc = summary['account']
        print(f"Balance: ${acc['balance']}")
        print(f"NAV (Equity): ${acc['NAV']}")
        print(f"PnL (Unrealized): ${acc['unrealizedPL']}")
    else:
        print("Error fetching summary:", summary)
        return

    print("\n--- OPEN POSITIONS ---")
    pos_resp = get_open_positions()
    if 'positions' in pos_resp:
        positions = pos_resp['positions']
        found_open = False
        for p in positions:
            long_units = int(p.get('long', {}).get('units', 0))
            short_units = int(p.get('short', {}).get('units', 0))
            if long_units != 0 or short_units != 0:
                found_open = True
                print(f"Instrument: {p['instrument']} | Long Units: {long_units} | Short Units: {short_units} | PnL: {p.get('unrealizedPL', '0.0')}")
        if not found_open:
            print("No open positions.")
    else:
        print("Error fetching positions:", pos_resp)

    print("\n--- RECENT CLOSED TRADES ---")
    trades_resp = get_closed_trades()
    if 'trades' in trades_resp:
        trades = trades_resp['trades']
        if not trades:
            print("No closed trades found in the last batch.")
        # Filter for March 23, 2026
        for t in trades:
            print(f"ID: {t['id']} | Instrument: {t['instrument']} | Units: {t['initialUnits']} | PnL: {t['realizedPL']} | Closed: {t['closeTime']}")
    else:
        print("Error fetching trades:", trades_resp)

if __name__ == "__main__":
    main()
