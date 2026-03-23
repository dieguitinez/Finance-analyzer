"""
⚖️ NIVO FX: BATTLE OF STRATEGIES (Legacy vs Stable vs Hybrid)
============================================================
Compares:
  1. LEGACY   : Multi-indicator weighted scoring (MACD, RSI, BB, etc.) - The first system.
  2. STABLE   : Pure Donchian 50 Breakout (Shanghai) - The current production system.
  3. HYBRID   : Donchian 50 Trigger + Legacy 75% Filter - The new v3.0 system.

Usage:
  $env:PYTHONUTF8="1"
  python backtest_comparison.py --pair EUR/USD --months 6
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import yfinance as yf
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 1: LEGACY (Weighted Logic)
# ─────────────────────────────────────────────────────────────────────────────
class LegacyBrain:
    def __init__(self, df):
        self.df = df.copy()
        self._calc()
    def _calc(self):
        self.df['EMA_200'] = self.df['Close'].ewm(span=200, adjust=False).mean()
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        self.df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD'] = ema12 - ema26
        self.df['MACD_S'] = self.df['MACD'].ewm(span=9, adjust=False).mean()
        tr = pd.concat([self.df['High']-self.df['Low'], abs(self.df['High']-self.df['Close'].shift()), abs(self.df['Low']-self.df['Close'].shift())], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(14).mean()

    def analyze(self):
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        score_long = 0
        score_short = 0
        # Simple weighted logic excerpt from original legacy code
        if last['Close'] > last['EMA_200']: score_long += 3
        else: score_short += 3
        if last['MACD'] > last['MACD_S']: score_long += 2
        else: score_short += 2
        if last['RSI'] < 40: score_long += 2
        elif last['RSI'] > 60: score_short += 2
        
        final_score = 50 + (score_long * 5) if score_long > score_short else 50 - (score_short * 5)
        signal = "WAIT"
        if final_score >= 80: signal = "BUY"
        elif final_score <= 20: signal = "SELL"
        return {"signal": signal, "current_price": last['Close'], "stop_loss": last['Close'] - (1.5 * last['ATR']) if signal == "BUY" else last['Close'] + (1.5 * last['ATR'])}

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 2: STABLE (Donchian Only)
# ─────────────────────────────────────────────────────────────────────────────
class StableBrain:
    def __init__(self, df):
        self.df = df.copy()
        self._calc()
    def _calc(self):
        self.df['D_H'] = self.df['High'].rolling(window=50).max().shift(1)
        self.df['D_L'] = self.df['Low'].rolling(window=50).min().shift(1)
        tr = pd.concat([self.df['High']-self.df['Low'], abs(self.df['High']-self.df['Close'].shift()), abs(self.df['Low']-self.df['Close'].shift())], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(14).mean()
    def analyze(self):
        last = self.df.iloc[-1]
        if last['Close'] > last['D_H']: return {"signal": "BUY", "current_price": last['Close'], "stop_loss": last['Close'] - (2.0 * last['ATR'])}
        if last['Close'] < last['D_L']: return {"signal": "SELL", "current_price": last['Close'], "stop_loss": last['Close'] + (2.0 * last['ATR'])}
        return {"signal": "WAIT"}

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 3: HYBRID (v3.0 - Fused)
# ─────────────────────────────────────────────────────────────────────────────
from src.nivo_trade_brain import NivoTradeBrain as HybridBrainLogic
class HybridBrain:
    def __init__(self, df): self.df = df
    def analyze(self):
        brain = HybridBrainLogic(self.df)
        res = brain.analyze_market()
        return {"signal": res['signal'], "current_price": res['current_price'], "stop_loss": res['stop_loss']}

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATOR ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def run_comparison(pair, months):
    symbol = pair.replace("/", "") + "=X"
    print(f"📥 Downloading data for {pair}...")
    df = yf.download(symbol, period=f"{months*30}d", interval="1h", progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.dropna()

    strategies = {
        "LEGACY (High Freq)": LegacyBrain,
        "STABLE (Donchian/Shanghai)": StableBrain,
        "HYBRID (v3.0 Fused)": HybridBrain
    }

    report = []
    forward = 12 # 12 bars window

    for name, BrainClass in strategies.items():
        print(f"🚀 Simulating {name}...")
        results = []
        for i in range(210, len(df) - forward):
            window = df.iloc[:i+1]
            brain = BrainClass(window)
            res = brain.analyze() if hasattr(brain, 'analyze') else brain.analyze_market()
            sig = res.get("signal", "WAIT")
            if sig not in ("BUY", "SELL", "STRONG BUY", "STRONG SELL"): continue
            
            sig_type = "BUY" if "BUY" in sig else "SELL"
            entry = float(res['current_price'])
            sl = float(res['stop_loss'])
            future = df['Close'].iloc[i+1 : i+1+forward]
            
            pip_f = 100 if "JPY" in pair else 10000
            
            # --- VOLATILITY PARITY SIMULATION ---
            sl_distance_pips = abs(entry - sl) * pip_f
            if sl_distance_pips == 0: sl_distance_pips = 1.0
            
            # Fixed Risk parameter
            risk_usd = 20.0
            pip_value = 1.0 / pip_f # Simplified approximation
            
            # Units sizing algorithm matches auto_execution.py
            units = risk_usd / (sl_distance_pips * pip_value)
            
            # Trade Outcome Simulation
            if sig_type == "BUY":
                hit_sl = future.min() <= sl
                # profit in pips
                profit_pips = (future.max() - entry) * pip_f if not hit_sl else (sl - entry) * pip_f
            else:
                hit_sl = future.max() >= sl
                # profit in pips
                profit_pips = (entry - future.min()) * pip_f if not hit_sl else (entry - sl) * pip_f
            
            # Convert Pips to Realized USD relative to Dynamic Position Size
            profit_usd = (profit_pips * pip_value) * units
            
            results.append(profit_usd)
        
        if results:
            wins = [r for r in results if r > 0]
            losses = [r for r in results if r <= 0]
            report.append({
                "Name": name,
                "Trades": len(results),
                "Win Rate": f"{len(wins)/len(results)*100:.1f}%",
                "Avg Win": f"${sum(wins)/len(wins):.2f}" if wins else "$0",
                "Avg Loss": f"${sum(losses)/len(losses):.2f}" if losses else "$0",
                "Net Profit": f"${sum(results):.2f}"
            })
        else:
            report.append({"Name": name, "Trades": 0, "Win Rate": "0%", "Avg Win": "$0", "Avg Loss": "$0", "Net Profit": "$0"})

    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", default="EUR/USD")
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()

    results = run_comparison(args.pair, args.months)
    
    print("\n" + "="*90)
    print(f"🏆 STRATEGY BENCHMARK REPORT - {args.pair} ({args.months} Months) - Volatility Parity Risk: $20/Trade")
    print("="*90)
    print(f"{'Strategy Name':<30} {'Trades':<10} {'Win Rate':<12} {'Avg Win':<12} {'Avg Loss':<12} {'Net Profit':<15}")
    print("-" * 90)
    for r in results:
        print(f"{r['Name']:<30} {r['Trades']:<10} {r['Win Rate']:<12} {r['Avg Win']:<12} {r['Avg Loss']:<12} {r['Net Profit']:<15}")
    print("="*90)
    print("\n💡 VERDICT: El sistema HYBRID V4 usa Paridad de Volatilidad, limitando las pérdidas promedio exactamente al riesgo definido ($20).")
