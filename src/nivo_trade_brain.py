import pandas as pd
import numpy as np

class NivoTradeBrain:
    """
    Core Logic Engine: Quantitative Trend-Following (Donchian / Turtle System)
    Focuses on 50-period breakouts and 20-period dynamic trailing stops.
    """

    def __init__(self, dataframe):
        self.df = dataframe.copy()
        self._calculate_indicators()

    def _calculate_indicators(self):
        """
        Calculates Donchian Channels and Volatility (ATR) for strict trend following.
        """
        # 1. 50-Period Breakout Channels (For Entry)
        # We shift(1) to compare the CURRENT close against the highest high of the PREVIOUS 50 periods.
        self.df['Donchian_High_50'] = self.df['High'].rolling(window=50).max().shift(1)
        self.df['Donchian_Low_50'] = self.df['Low'].rolling(window=50).min().shift(1)

        # 2. 20-Period Breakout Channels (For Trailing Stop / Exit Structure)
        self.df['Donchian_High_20'] = self.df['High'].rolling(window=20).max().shift(1)
        self.df['Donchian_Low_20'] = self.df['Low'].rolling(window=20).min().shift(1)

        # 3. ATR (Average True Range) - For Volatility-based Stop Loss
        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['ATR'] = ranges.rolling(window=20).mean() # 20 period ATR is standard for Turtle
        
        # 4. Standard EMAs just for visual context in the UI (Not used for triggering)
        self.df['EMA_50'] = self.df['Close'].ewm(span=50, adjust=False).mean()
        self.df['EMA_200'] = self.df['Close'].ewm(span=200, adjust=False).mean()
        self.df['RSI'] = 50 # Dummy values to prevent UI crashes if it looks for RSI
        self.df['ADX'] = np.nan

    def analyze_market(self):
        """
        Analyzes the LAST available candle to detect 50-period trend breakouts.
        Returns strict signals based on the Momentum/Trend-Following expectancy equations.
        """
        if len(self.df) < 55:
            return {"score": 50, "signal": "INSUFFICIENT DATA", "reasons": ["Need at least 55 bars for Donchian 50"]}

        last = self.df.iloc[-1]
        
        reasons = []
        signal = "WAIT"
        final_score = 50
        is_long = False
        
        current_close = last['Close']
        high_50 = last['Donchian_High_50']
        low_50 = last['Donchian_Low_50']
        atr = last['ATR']

        # --- DONCHIAN BREAKOUT LOGIC ---
        
        # LONG ENTRY: Price breaks above the highest high of the last 50 periods
        if current_close > high_50:
            signal = "BUY"
            final_score = 100  # Max conviction breakout
            is_long = True
            reasons.append(f"🚀 Bullish Breakout: Close ({current_close:.5f}) > 50-Period High ({high_50:.5f})")

        # SHORT ENTRY: Price breaks below the lowest low of the last 50 periods
        elif current_close < low_50:
            signal = "SELL"
            final_score = 0  # Max conviction breakdown
            is_long = False
            reasons.append(f"📉 Bearish Breakout: Close ({current_close:.5f}) < 50-Period Low ({low_50:.5f})")
            
        else:
            reasons.append("⏳ Inside Range. No breakout detected.")

        # --- RISK MANAGEMENT CALCULATION ---
        # Stop Loss initial distance is 2.0 * ATR
        sl_distance = 2.0 * atr
        
        if is_long:
            stop_loss = current_close - sl_distance
        elif signal == "SELL":
            stop_loss = current_close + sl_distance
        else:
            stop_loss = 0.0

        return {
            "score": final_score,
            "signal": signal,
            "direction": "LONG" if is_long else "SHORT",
            "is_pullback": False, # Deprecated in Trend Following
            "pullback_type": None,
            "confidence": "Max" if signal != "WAIT" else "Neutral",
            "current_price": float(current_close),
            "stop_loss": float(stop_loss),
            "take_profit": 0.0, # Handled dynamically by Trailing Stops
            "atr": float(atr),
            "donchian_lower_20": float(last['Donchian_Low_20']),
            "donchian_upper_20": float(last['Donchian_High_20']),
            "reasons": reasons
        }
