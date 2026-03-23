import pandas as pd
import numpy as np

class NivoTradeBrain:
    """
    Hybrid Logic Engine: Combines the stability of Donchian Breakouts (Trigger)
    with the mathematical robustness of the Legacy Weighted Scorer (Filter).
    """

    def __init__(self, dataframe):
        self.df = dataframe.copy()
        self._calculate_indicators()

    def _calculate_indicators(self):
        """
        Calculates both Donchian Channels (for the trigger) and the 
        Legacy indicators (ADX, MACD, BB, RSI, EMA) for the confirmation score.
        """
        # ==========================================
        # PART 1: THE TRIGGER (Donchian Channels & ATR)
        # ==========================================
        self.df['Donchian_High_50'] = self.df['High'].rolling(window=50).max().shift(1)
        self.df['Donchian_Low_50'] = self.df['Low'].rolling(window=50).min().shift(1)
        self.df['Donchian_High_20'] = self.df['High'].rolling(window=20).max().shift(1)
        self.df['Donchian_Low_20'] = self.df['Low'].rolling(window=20).min().shift(1)

        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['ATR'] = ranges.rolling(window=20).mean()

        # ==========================================
        # PART 2: THE FILTER (Legacy Scoring Indicators)
        # ==========================================
        self.df['EMA_50'] = self.df['Close'].ewm(span=50, adjust=False).mean()
        self.df['EMA_200'] = self.df['Close'].ewm(span=200, adjust=False).mean()

        # RSI 14
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))

        # Bollinger Bands (20, 2)
        self.df['SMA_20'] = self.df['Close'].rolling(window=20).mean()
        self.df['BB_Std'] = self.df['Close'].rolling(window=20).std()
        self.df['BB_Upper'] = self.df['SMA_20'] + (self.df['BB_Std'] * 2)
        self.df['BB_Lower'] = self.df['SMA_20'] - (self.df['BB_Std'] * 2)

        # MACD (12, 26, 9)
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD'] = ema12 - ema26
        self.df['MACD_Signal'] = self.df['MACD'].ewm(span=9, adjust=False).mean()

        # ADX 14
        plus_dm = self.df['High'].diff()
        minus_dm = self.df['Low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = pd.concat([self.df['High'] - self.df['Low'],
                       (self.df['High'] - self.df['Close'].shift()).abs(),
                       (self.df['Low'] - self.df['Close'].shift()).abs()], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / (atr_14 + 1e-9))
        minus_di = 100 * (abs(minus_dm.rolling(14).mean()) / (atr_14 + 1e-9))
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
        self.df['ADX'] = pd.Series(dx).rolling(14).mean()

    def analyze_market(self):
        """
        Analyzes the LAST available candle.
        Step 1: Check for Donchian 50 Breakout.
        Step 2: If broken, calculate Legacy Score to confirm conviction.
        """
        if len(self.df) < 200:
            return {"score": 0, "signal": "INSUFFICIENT DATA", "reasons": ["Need at least 200 bars for EMA200"]}

        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        current_close = last['Close']
        high_50 = last['Donchian_High_50']
        low_50 = last['Donchian_Low_50']
        atr = last['ATR']
        
        reasons = []
        signal = "WAIT"
        final_score = 50
        is_long = False

        # --- STEP 1: DONCHIAN TRIGGER ---
        is_bullish_breakout = current_close > high_50
        is_bearish_breakout = current_close < low_50

        if not is_bullish_breakout and not is_bearish_breakout:
            reasons.append("⏳ Inside Range. No Donchian 50 breakout detected.")
            return self._build_response(signal, final_score, is_long, current_close, atr, reasons, last)

        if is_bullish_breakout:
            reasons.append(f"🚀 Bullish Breakout: Close ({current_close:.5f}) > 50-High ({high_50:.5f})")
            is_long = True
            direction_bias = "LONG"
        else:
            reasons.append(f"📉 Bearish Breakout: Close ({current_close:.5f}) < 50-Low ({low_50:.5f})")
            is_long = False
            direction_bias = "SHORT"

        # --- STEP 2: LEGACY CONFIRMATION SCORE ---
        score_pts = 0
        max_possible = 10.0
        
        # 1. Macro Trend Filter (EMA 200) - 3.0 pts
        if is_long and current_close > last['EMA_200']:
            score_pts += 3.0
            reasons.append("✅ Above EMA 200 (Aligns with Long)")
        elif not is_long and current_close < last['EMA_200']:
            score_pts += 3.0
            reasons.append("✅ Below EMA 200 (Aligns with Short)")

        # 2. RSI Momentum - 2.0 pts
        # En ruptura queremos fuerza direccional, no divergencia.
        if is_long and last['RSI'] > 50:
            score_pts += 2.0
            reasons.append("✅ RSI > 50 (Bullish Momentum)")
        elif not is_long and last['RSI'] < 50:
            score_pts += 2.0
            reasons.append("✅ RSI < 50 (Bearish Momentum)")

        # 3. MACD Crossover / Alignment - 3.0 pts
        if is_long and last['MACD'] > last['MACD_Signal']:
            score_pts += 3.0
            reasons.append("✅ MACD Bullish Alignment")
        elif not is_long and last['MACD'] < last['MACD_Signal']:
            score_pts += 3.0
            reasons.append("✅ MACD Bearish Alignment")

        # 4. Volatility (ADX) - 2.0 pts
        if last['ADX'] > 25:
            score_pts += 2.0
            reasons.append("✅ Strong Trend Strength (ADX > 25)")

        # Scale 0-10 to 50-100 (for Long) or 50-0 (for Short) matching Legacy output style
        # Actually, let's just make final_score absolute 0-100 logic for both, 
        # Since vm_executor expects >80 for strong signals, etc.
        # But wait, vm_executor (stable) takes final_score = 100 for absolute BUY and 0 for absolute SELL.
        percentage_score = (score_pts / max_possible) * 100  # 0 to 100% conviction of the breakout
        
        if is_long:
            final_score = 50 + (percentage_score / 2) # Maps 0-100 conviction to 50-100 score
        else:
            final_score = 50 - (percentage_score / 2) # Maps 0-100 conviction to 50-0 score
            
        # VETO THRESHOLD: We require at least 65% conviction on the legacy metrics
        # Long: 50 + (65/2) = 66.25 (Wait, the math in the old code said 75% -> 87.5. Let's follow that logic.)
        # 50 + (65/2) = 66.25? No, the legacy code used (pts/max)*100.
        # So 65% conviction means percentage_score >= 65.
        # 50 + (65/2) = 82.5. Correct.
        # 50 - (65/2) = 17.5. Correct.
        VETO_LONG_THRESHOLD = 82.5
        VETO_SHORT_THRESHOLD = 17.5
        
        if is_long and final_score >= VETO_LONG_THRESHOLD:
            signal = "BUY"
            reasons.append(f"🔥 Legacy Conviction: {percentage_score:.1f}% (Breakout Validated)")
        elif not is_long and final_score <= VETO_SHORT_THRESHOLD:
            signal = "SELL"
            reasons.append(f"🔥 Legacy Conviction: {percentage_score:.1f}% (Breakdown Validated)")
        else:
            signal = "WAIT"
            reasons.append(f"🛡️ FALSE BREAKOUT VETO: Legacy Conviction only {percentage_score:.1f}%. Need 65%. Trade Muted.")
            final_score = 50 # Reset score so vm_executor ignores it

        return self._build_response(signal, final_score, is_long, current_close, atr, reasons, last)

    def _build_response(self, signal, score, is_long, current_close, atr, reasons, last_row):
        sl_distance = 2.0 * atr

        if signal == "BUY":
            stop_loss = current_close - sl_distance
        elif signal == "SELL":
            stop_loss = current_close + sl_distance
        else:
            stop_loss = 0.0

        return {
            "score": float(score),
            "signal": signal,
            "direction": "LONG" if is_long else "SHORT",
            "is_pullback": False,
            "pullback_type": None,
            "confidence": f"{score:.1f}%" if signal != "WAIT" else "Neutral",
            "current_price": float(current_close),
            "stop_loss": float(stop_loss),
            "take_profit": 0.0,
            "atr": float(atr),
            "donchian_lower_20": float(last_row['Donchian_Low_20']),
            "donchian_upper_20": float(last_row['Donchian_High_20']),
            "reasons": reasons
        }
