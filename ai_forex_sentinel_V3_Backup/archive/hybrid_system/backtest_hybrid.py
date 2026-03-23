"""
🧪 NIVO FX HYBRID BACKTEST SIMULATOR v1.0
==========================================
Runs the Hybrid Logic (Gate 1: Donchian 50 + Gate 2: Legacy Score >75%)
against real historical H1 candles to answer:
  - How many times would the bot have signaled BUY/SELL?
  - Were those signals profitable (price moved in the right direction)?

NOTE: This simulates ONLY the 2 mathematical gates. It does NOT simulate
Gate 3 (LSTM) or Gate 4 (News) since historical AI probabilities don't exist.
This gives us a CONSERVATIVE estimate (real system would fire even LESS).

Usage:
  cd hybrid_system
  python backtest_hybrid.py --pair EUR/USD --months 6 --forward_bars 12
"""

import sys
import os
import argparse

# Ensure src is importable from hybrid_system folder
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import yfinance as yf
import pandas as pd
from src.nivo_trade_brain import NivoTradeBrain

# ── Yahoo Finance symbol mapping ───────────────────────────────────────────
PAIR_MAP = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "USD/CHF": "USDCHF=X",
}

def fetch_historical(pair: str, months: int) -> pd.DataFrame:
    symbol = PAIR_MAP.get(pair.upper(), pair)
    period = f"{months * 30}d"
    print(f"[DOWNLOAD] Descargando {months} meses de datos H1 para {pair} ({symbol})...")
    df = yf.download(symbol, period=period, interval="1h", progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low",
                             "Close": "Close", "Volume": "Volume"})
    df = df.dropna()
    print(f"  -> {len(df)} velas descargadas ({df.index[0].date()} a {df.index[-1].date()})")
    return df

def run_backtest(df: pd.DataFrame, forward_bars: int = 12):
    """
    Walks through each candle (after we have enough history) and checks
    if the hybrid brain would have fired a signal.
    Then checks the next `forward_bars` candles to see if price moved
    in the right direction (naive win/loss).
    """
    MIN_BARS = 210  # Need 200 for EMA200 + some buffer
    signals = []

    print(f"\n🔍 Analizando {len(df) - MIN_BARS} velas con la Lógica Híbrida...\n")

    for i in range(MIN_BARS, len(df) - forward_bars):
        window = df.iloc[:i+1].copy()
        try:
            brain = NivoTradeBrain(window)
            result = brain.analyze_market()
        except Exception as e:
            continue

        signal = result.get("signal", "WAIT")
        if signal not in ("BUY", "SELL"):
            continue

        # Check outcome: did price move in the right direction?
        entry_price = result.get("current_price", window['Close'].iloc[-1])
        sl_price = result.get("stop_loss", 0)
        candle_time = df.index[i]

        future_closes = df['Close'].iloc[i+1 : i+1+forward_bars]
        max_future = float(future_closes.max())
        min_future = float(future_closes.min())

        if signal == "BUY":
            hit_sl = min_future <= sl_price
            moved_favorably = max_future > entry_price
            pips = (max_future - entry_price) * 10000
        else:  # SELL
            hit_sl = max_future >= sl_price
            moved_favorably = min_future < entry_price
            pips = (entry_price - min_future) * 10000

        outcome = "❌ SL" if hit_sl else ("✅ WIN" if moved_favorably else "➡️ FLAT")
        reasons_summary = "; ".join(result.get("reasons", [])[:3])

        signals.append({
            "time": candle_time,
            "signal": signal,
            "entry": round(float(entry_price), 5),
            "sl": round(float(sl_price), 5),
            "score": round(result.get("score", 0), 1),
            "pips": round(pips, 1),
            "outcome": outcome,
            "reasons": reasons_summary,
        })

    return signals

def print_summary(signals, pair, forward_bars):
    if not signals:
        print("=" * 60)
        print("⚠️  CERO señales generadas.")
        print("   El sistema es MUY estricto. Considera:")
        print("   → Bajar el umbral de Score de 75% a 65%")
        print("   → Ampliar el periodo de análisis a 12 meses")
        print("=" * 60)
        return

    wins   = [s for s in signals if "WIN" in s["outcome"]]
    losses = [s for s in signals if "SL" in s["outcome"]]
    flats  = [s for s in signals if "FLAT" in s["outcome"]]
    buys   = [s for s in signals if s["signal"] == "BUY"]
    sells  = [s for s in signals if s["signal"] == "SELL"]
    win_rate = len(wins) / len(signals) * 100 if signals else 0

    print("\n" + "=" * 60)
    print(f"📊 RESULTADOS DEL BACKTEST — {pair} (H1, ventana: {forward_bars} barras)")
    print("=" * 60)
    print(f"  Total señales detectadas : {len(signals)}")
    print(f"  BUY signals              : {len(buys)}")
    print(f"  SELL signals             : {len(sells)}")
    print(f"  ✅ Win (precio favoreció): {len(wins)}")
    print(f"  ❌ Stop Loss tocado      : {len(losses)}")
    print(f"  ➡️  Flat (sin movimiento) : {len(flats)}")
    print(f"  Win Rate (simple)        : {win_rate:.1f}%")
    print("=" * 60)

    print("\n📋 DETALLE DE SEÑALES:")
    print(f"{'Fecha/Hora':<22} {'Señal':<6} {'Entrada':>9} {'SL':>9} {'Pips':>7} {'Resultado':<10}")
    print("-" * 70)
    for s in signals[-30:]:  # Show last 30 max
        t = str(s["time"])[:16]
        print(f"{t:<22} {s['signal']:<6} {s['entry']:>9.5f} {s['sl']:>9.5f} {s['pips']:>7.1f} {s['outcome']:<10}")

    if len(signals) > 30:
        print(f"  ... ({len(signals) - 30} señales más no mostradas)")

    print("\n🔎 DIAGNÓSTICO:")
    freq = len(signals) / 6  # approx signals per month
    if freq < 1:
        print("  ⚠️  Frecuencia MUY baja (<1/mes). El sistema puede ser demasiado estricto.")
        print("  💡 Sugerencia: Bajar umbral Legacy Score de 75% a 60-65%.")
    elif freq < 4:
        print("  ✅ Frecuencia saludable (1-4/mes). Calidad > Cantidad. Buen equilibrio.")
    else:
        print("  ⚡ Frecuencia alta (>4/mes). Monitorear si hay demasiado ruido.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nivo FX Hybrid Backtest")
    parser.add_argument("--pair", default="EUR/USD", help="Par de divisas (ej. EUR/USD)")
    parser.add_argument("--months", type=int, default=6, help="Meses de historia a analizar")
    parser.add_argument("--forward_bars", type=int, default=12,
                        help="Velas H1 futuras para evaluar resultado (default 12 = 12h)")
    args = parser.parse_args()

    df = fetch_historical(args.pair, args.months)
    signals = run_backtest(df, forward_bars=args.forward_bars)
    print_summary(signals, args.pair, args.forward_bars)
