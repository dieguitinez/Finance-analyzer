"""
🧪 NIVO FX MULTI-PAIR BACKTEST + PIP PROFITABILITY REPORT
==========================================================
Scans ALL pairs in the watchlist and reports:
  - Signal count per pair
  - Average PIPS won vs average PIPS lost
  - Net Expected Value per trade

Usage:
  $env:PYTHONUTF8="1"
  python backtest_all_pairs.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import yfinance as yf
import pandas as pd
from src.nivo_trade_brain import NivoTradeBrain

WATCHLIST = [
    ("EUR/USD","EURUSD=X"), ("GBP/USD","GBPUSD=X"), ("USD/JPY","USDJPY=X"),
    ("USD/CAD","USDCAD=X"), ("AUD/USD","AUDUSD=X"), ("USD/CHF","USDCHF=X"),
    ("NZD/USD","NZDUSD=X"), ("EUR/GBP","EURGBP=X"), ("EUR/JPY","EURJPY=X"),
    ("GBP/JPY","GBPJPY=X"), ("EUR/CHF","EURCHF=X"), ("CHF/JPY","CHFJPY=X"),
    ("AUD/JPY","AUDJPY=X"), ("NZD/JPY","NZDJPY=X"), ("EUR/AUD","EURAUD=X"),
]
FORWARD_BARS = 12   # 12 hours to evaluate trade outcome
MONTHS       = 6
MIN_BARS     = 210
PIP_FACTOR   = 100 if "JPY" else 10000  # adjusted per-pair below

def is_jpy(pair): return "JPY" in pair

def fetch(pair_label, symbol):
    period = f"{MONTHS * 30}d"
    try:
        df = yf.download(symbol, period=period, interval="1h", progress=False)
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(columns={"Open":"Open","High":"High","Low":"Low","Close":"Close"})
        return df.dropna()
    except Exception as e:
        print(f"  [ERROR] {pair_label}: {e}")
        return pd.DataFrame()

def backtest_pair(pair_label, df):
    pip = 100 if is_jpy(pair_label) else 10000
    results = []
    for i in range(MIN_BARS, len(df) - FORWARD_BARS):
        window = df.iloc[:i+1].copy()
        try:
            brain  = NivoTradeBrain(window)
            result = brain.analyze_market()
        except:
            continue
        signal = result.get("signal", "WAIT")
        if signal not in ("BUY", "SELL"):
            continue

        entry  = float(result.get("current_price", df['Close'].iloc[i]))
        sl     = float(result.get("stop_loss", 0))
        future = df['Close'].iloc[i+1: i+1+FORWARD_BARS]

        if signal == "BUY":
            best   = float(future.max())
            worst  = float(future.min())
            pips_if_win   = (best  - entry) * pip
            pips_if_loss  = (entry - worst) * pip
            hit_sl = worst <= sl
        else:
            best   = float(future.min())
            worst  = float(future.max())
            pips_if_win   = (entry - best)  * pip
            pips_if_loss  = (worst - entry) * pip
            hit_sl = worst >= sl

        moved_fav = (signal == "BUY" and float(future.max()) > entry) or \
                    (signal == "SELL" and float(future.min()) < entry)

        if hit_sl:
            outcome   = "SL"
            pips_real = -pips_if_loss
        elif moved_fav:
            outcome   = "WIN"
            pips_real = pips_if_win
        else:
            outcome   = "FLAT"
            pips_real = 0.0

        results.append({
            "signal"    : signal,
            "outcome"   : outcome,
            "pips"      : round(pips_real, 1),
        })
    return results

def summarize(pair_label, results):
    if not results:
        return {"pair": pair_label, "n": 0, "wr": 0, "avg_win": 0,
                "avg_loss": 0, "ev": 0}
    wins   = [r["pips"] for r in results if r["outcome"] == "WIN"]
    losses = [r["pips"] for r in results if r["outcome"] == "SL"]
    n      = len(results)
    wr     = len(wins) / n * 100
    avg_w  = sum(wins)   / len(wins)   if wins   else 0
    avg_l  = sum(losses) / len(losses) if losses else 0   # already negative
    ev     = (wr/100 * avg_w) + ((1-wr/100) * avg_l)
    ev     = round(ev, 1)
    return {
        "pair": pair_label, "n": n,
        "buys": sum(1 for r in results if r["signal"]=="BUY"),
        "sells": sum(1 for r in results if r["signal"]=="SELL"),
        "wr": round(wr,1),
        "avg_win": round(avg_w,1),
        "avg_loss": round(avg_l,1),
        "ev": ev,
    }

print("=" * 72)
print("  NIVO FX HYBRID — MULTI-PAIR BACKTEST (6 meses H1, forward=12h)")
print("=" * 72)

all_summaries = []
for pair_label, symbol in WATCHLIST:
    print(f"  Escaneando {pair_label}...", end=" ", flush=True)
    df = fetch(pair_label, symbol)
    if len(df) < MIN_BARS + FORWARD_BARS:
        print("NO DATA")
        continue
    results = backtest_pair(pair_label, df)
    s = summarize(pair_label, results)
    all_summaries.append(s)
    print(f"{s['n']} senal(es) | WR: {s['wr']}% | Avg Win: {s['avg_win']} pips | Avg Loss: {s['avg_loss']} pips | EV: {s['ev']} pips")

print()
print("=" * 72)
print(f"  {'PAR':<12} {'N':>4} {'BUY':>5} {'SELL':>5} {'WR%':>6} {'Avg Win':>9} {'Avg Loss':>9} {'EV/trade':>9}")
print("-" * 72)
for s in sorted(all_summaries, key=lambda x: x.get("ev",0), reverse=True):
    ev_sym = "+" if s["ev"] > 0 else ""
    print(f"  {s['pair']:<12} {s['n']:>4} {s.get('buys',0):>5} {s.get('sells',0):>5} {s['wr']:>5.1f}% {s['avg_win']:>9.1f} {s['avg_loss']:>9.1f} {ev_sym}{s['ev']:>8.1f}")

total_n  = sum(s["n"] for s in all_summaries)
avg_wr   = sum(s["wr"] * s["n"] for s in all_summaries) / total_n if total_n else 0
avg_ev   = sum(s["ev"] * s["n"] for s in all_summaries) / total_n if total_n else 0
print("-" * 72)
print(f"  {'TOTAL/AVG':<12} {total_n:>4}                 {avg_wr:>5.1f}%                    {'+' if avg_ev>0 else ''}{avg_ev:>8.1f}")
print("=" * 72)
print()
print("  VERDICT:")
profitable = [s for s in all_summaries if s["ev"] > 0]
unprofitable = [s for s in all_summaries if s["ev"] <= 0]
print(f"  -> Pares con expectativa POSITIVA : {len(profitable)}: {', '.join(s['pair'] for s in profitable)}")
print(f"  -> Pares con expectativa NEGATIVA : {len(unprofitable)}: {', '.join(s['pair'] for s in unprofitable)}")
if avg_ev > 0:
    print(f"  -> El sistema hibrido tiene EDGE POSITIVO promedio de +{avg_ev:.1f} pips/operacion.")
else:
    print(f"  -> Cuidado: EV negativo promedio de {avg_ev:.1f} pips. Revisar filtros.")
