"""
Nivo FX — OANDA Historical Data Downloader
==========================================
Downloads 2 years of H1 (hourly) candle data for all 15 monitored pairs.
Saves as CSV files in scripts/data/ for LSTM training.
After training, CSVs can be safely deleted (only .pth files are needed for inference).

Usage (run from project root on Linux server):
    cd /home/diego/nivo_fx
    source .venv/bin/activate
    python3 scripts/download_oanda_data.py
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────
TOKEN    = os.getenv("OANDA_ACCESS_TOKEN")
BASE_URL = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
HEADERS  = {"Authorization": f"Bearer {TOKEN}"}

# All 15 pairs monitored by the sentinel
PAIRS = [
    # Majors (trained before)
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD",
    # Additional majors
    "USD_CAD", "USD_CHF", "NZD_USD",
    # JPY crosses
    "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY", "CHF_JPY",
    # Other crosses
    "EUR_GBP", "EUR_CHF", "EUR_AUD",
]

TIMEFRAME   = "H1"          # Hourly candles
YEARS_BACK  = 2             # 2 years of history
CANDLES_PER_REQUEST = 4000  # OANDA max per call

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Fetcher ─────────────────────────────────────────────────────────────────
def fetch_candles(pair: str, from_dt: datetime, to_dt: datetime) -> list:
    """Fetches candle data in paginated chunks of CANDLES_PER_REQUEST."""
    all_candles = []
    current_from = from_dt

    while current_from < to_dt:
        params = {
            "granularity": TIMEFRAME,
            "from": current_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": CANDLES_PER_REQUEST,
            "price": "M"  # Mid prices
        }

        try:
            r = requests.get(
                f"{BASE_URL}/v3/instruments/{pair}/candles",
                headers=HEADERS, params=params, timeout=30
            )
            r.raise_for_status()
            candles = r.json().get("candles", [])

            if not candles:
                break

            all_candles.extend(candles)
            print(f"  [{pair}] Fetched {len(all_candles)} candles so far...")

            # Advance window to last candle + 1 hour
            last_time = candles[-1]["time"]
            current_from = datetime.fromisoformat(last_time.replace("Z", "+00:00")) + timedelta(hours=1)

            if len(candles) < CANDLES_PER_REQUEST:
                break  # No more data available

            time.sleep(0.3)  # Respect rate limits

        except Exception as e:
            print(f"  [{pair}] ERROR: {e}")
            break

    return all_candles


def candles_to_df(candles: list) -> pd.DataFrame:
    """Converts raw OANDA candle list to a clean OHLCV DataFrame."""
    rows = []
    for c in candles:
        if not c.get("complete", True):
            continue
        mid = c.get("mid", {})
        rows.append({
            "Datetime": c["time"],
            "Open":  float(mid.get("o", 0)),
            "High":  float(mid.get("h", 0)),
            "Low":   float(mid.get("l", 0)),
            "Close": float(mid.get("c", 0)),
            "Volume": int(c.get("volume", 0))
        })
    df = pd.DataFrame(rows)
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.set_index("Datetime").sort_index()
    return df


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        print("❌ ERROR: OANDA_ACCESS_TOKEN not found in .env")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    two_years_ago = now - timedelta(days=365 * YEARS_BACK)

    print(f"\n🔽 Nivo FX — Downloading {YEARS_BACK} years of {TIMEFRAME} data")
    print(f"   Period: {two_years_ago.date()} → {now.date()}")
    print(f"   Pairs:  {', '.join(PAIRS)}\n")

    for pair in PAIRS:
        print(f"\n📊 Downloading {pair}...")
        candles = fetch_candles(pair, two_years_ago, now)

        if not candles:
            print(f"  ⚠️  No data returned for {pair}")
            continue

        df = candles_to_df(candles)
        out_path = os.path.join(OUTPUT_DIR, f"{pair}_H1.csv")
        df.to_csv(out_path)
        print(f"  ✅ Saved {len(df)} candles → {out_path}")

    print(f"\n✅ Download complete! Files saved to: {OUTPUT_DIR}")
    print("   Next step: run  python3 scripts/train_lstm.py")


if __name__ == "__main__":
    main()
