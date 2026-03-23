import pandas as pd
import numpy as np

class NivoTradeBrain:
    """
    Hybrid Logic Engine: Combines the stability of Donchian Breakouts (Trigger)
    with the mathematical robustness of the Legacy Weighted Scorer (Filter).
    """

    def __init__(self, dataframe):
        self.df = dataframe
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

        # ==========================================
        # PART 3: ADVANCED V4 INDICATORS
        # ==========================================
        
        # 1. EMA 20 & Slope (Pendiente)
        self.df['EMA_20'] = self.df['Close'].ewm(span=20, adjust=False).mean()
        # Pendiente: Diferencia porcentual entre el punto actual y el de hace 3 velas
        self.df['EMA_20_Slope'] = (self.df['EMA_20'].diff(3) / self.df['EMA_20'].shift(3)) * 1000

        # 2. VWAP (Institutional Average Price)
        # Note: True VWAP requires intraday reset, here we use a rolling window of 100 periods for stability
        typical_price = (self.df['High'] + self.df['Low'] + self.df['Close']) / 3
        tp_v = typical_price * self.df['Volume']
        self.df['VWAP'] = tp_v.rolling(window=100).sum() / self.df['Volume'].rolling(window=100).sum()
        self.df['VWAP_Dist'] = (self.df['Close'] - self.df['VWAP']) / self.df['VWAP'] * 100

        # 3. Liquidity Map (Stop Loss Clusters)
        self._detect_liquidity_clusters()

    def _detect_liquidity_clusters(self, window=200, sensitivity=0.0005):
        """
        Identifies price zones where multiple Highs or Lows have clustered.
        Sensitivity: percentage range to consider a 'cluster'.
        """
        # We only calculate for the latest part of the dataframe to save resources
        if len(self.df) < window: return
        
        subset = self.df.iloc[-window:]
        highs = subset['High'].values
        lows = subset['Low'].values
        
        # Simple clustering: If multiple points are within 'sensitivity' of each other
        self.df['Liquidity_Zone_High'] = 0.0
        self.df['Liquidity_Zone_Low'] = 0.0
        
        # Analysis for Highs (Resistance Liquidity / Buy Stops)
        for h in highs[-20:]: # Check near latest price
            matches = np.sum(np.abs(subset['High'] - h) / h < sensitivity)
            if matches >= 3: # If 3 or more candles touched this area
                self.df.iloc[-1, self.df.columns.get_loc('Liquidity_Zone_High')] = h
                break
                
        # Analysis for Lows (Support Liquidity / Sell Stops)
        for l in lows[-20:]:
            matches = np.sum(np.abs(subset['Low'] - l) / l < sensitivity)
            if matches >= 3:
                self.df.iloc[-1, self.df.columns.get_loc('Liquidity_Zone_Low')] = l
                break

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

        # ==========================================
        # PART 4: V6 DIRECTIONAL GATING (IMPARTIAL TREND)
        # ==========================================
        ema_50 = last['EMA_50']
        ema_200 = last['EMA_200']
        
        # Determine Global Trend Mode
        if ema_50 > ema_200:
            trend_mode = "BULLISH_ONLY"
            reasons.append("🛡️ V6 TREND GATE: Bullish Stack (50 > 200). Longs Only Allowed.")
        else:
            trend_mode = "BEARISH_ONLY"
            reasons.append("🛡️ V6 TREND GATE: Bearish Stack (50 < 200). Shorts Only Allowed.")

        # --- STEP 1: DUAL DONCHIAN TRIGGER ---
        # Reduce window to 20 for initial trigger, use 50 for trend confirmation
        high_20 = last['Donchian_High_20']
        low_20 = last['Donchian_Low_20']
        
        is_bullish_breakout = current_close > high_20
        is_bearish_breakout = current_close < low_20

        if not is_bullish_breakout and not is_bearish_breakout:
            reasons.append("⏳ Consolidation. No Donchian 20 breakout detected.")
            return self._build_response(signal, final_score, is_long, current_close, atr, reasons, last)

        # --- STEP 2: IMPARTIAL TREND ALIGNMENT (THE V6 CORE) ---
        if is_bullish_breakout and trend_mode == "BEARISH_ONLY":
            reasons.append("🚫 VETO: Bullish Breakout ignored in Bearish Trend (Price < EMA 200).")
            return self._build_response("WAIT", 50, True, current_close, atr, reasons, last)
            
        if is_bearish_breakout and trend_mode == "BULLISH_ONLY":
            reasons.append("🚫 VETO: Bearish Breakout ignored in Bullish Trend (Price > EMA 200).")
            return self._build_response("WAIT", 50, False, current_close, atr, reasons, last)

        if is_bullish_breakout:
            reasons.append(f"🚀 Bullish Breakout: Close ({current_close:.5f}) > 20-High ({high_20:.5f})")
            is_long = True
        else:
            reasons.append(f"📉 Bearish Breakout: Close ({current_close:.5f}) < 20-Low ({low_20:.5f})")
            is_long = False

        # --- STEP 3: LEGACY CONFIRMATION SCORE ---
        score_pts = 0
        max_possible = 10.0
        
        # 1. Slope Confirmation (Momentum) - 3.0 pts
        slope = last['EMA_20_Slope']
        if is_long and slope > 0.05:
            score_pts += 3.0
            reasons.append(f"✅ Positive Slope ({slope:.3f})")
        elif not is_long and slope < -0.05:
            score_pts += 3.0
            reasons.append(f"✅ Negative Slope ({slope:.3f})")

        # 2. RSI Momentum - 2.0 pts
        if is_long and last['RSI'] > 55:
            score_pts += 2.0
            reasons.append("✅ RSI > 55 (Bullish Strength)")
        elif not is_long and last['RSI'] < 45:
            score_pts += 2.0
            reasons.append("✅ RSI < 45 (Bearish Strength)")

        # 3. MACD Alignment - 3.0 pts
        if is_long and last['MACD'] > last['MACD_Signal']:
            score_pts += 3.0
            reasons.append("✅ MACD Bullish")
        elif not is_long and last['MACD'] < last['MACD_Signal']:
            score_pts += 3.0
            reasons.append("✅ MACD Bearish")

        # 4. VWAP Position - 2.0 pts
        if is_long and current_close > last['VWAP']:
            score_pts += 2.0
            reasons.append("✅ Above Institutional VWAP")
        elif not is_long and current_close < last['VWAP']:
            score_pts += 2.0
            reasons.append("✅ Below Institutional VWAP")

        percentage_score = (score_pts / max_possible) * 100
        
        if is_long:
            final_score = 50 + (percentage_score / 2)
        else:
            final_score = 50 - (percentage_score / 2)
            
        VETO_LONG_THRESHOLD = 75.0
        VETO_SHORT_THRESHOLD = 25.0
        
        if is_long and final_score >= VETO_LONG_THRESHOLD:
            signal = "BUY"
            reasons.append(f"🔥 V6 Trend Confirmed: {percentage_score:.1f}% Conviction.")
        elif not is_long and final_score <= VETO_SHORT_THRESHOLD:
            signal = "SELL"
            reasons.append(f"🔥 V6 Trend Confirmed: {percentage_score:.1f}% Conviction.")
        else:
            signal = "WAIT"
            reasons.append(f"🛡️ LOW CONVICTION: Trend check passed but scoring only {percentage_score:.1f}%. Muted.")
            final_score = 50

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
