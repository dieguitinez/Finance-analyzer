import pandas as pd
import numpy as np

class NivoTradeBrain:
    """
    Core Logic Engine for Nivo FX Intelligence Suite.
    Implements manual vectorization for technical indicators to avoid 
    heavy dependencies like TA-Lib or pandas-ta.
    Optimized for Nivo Partners institutional standards.
    """

    def __init__(self, dataframe):
        # We work with a copy to avoid SettingWithCopy warnings on the original df
        self.df = dataframe.copy()
        self._calculate_indicators()

    def _calculate_indicators(self):
        """
        Internal method to calculate Technical Indicators using pure Pandas/Numpy.
        Protocol v2.0 Compliance: No external TA libraries.
        """
        # 1. EMAs (Exponential Moving Averages)
        self.df['EMA_50'] = self.df['Close'].ewm(span=50, adjust=False).mean()
        self.df['EMA_200'] = self.df['Close'].ewm(span=200, adjust=False).mean()

        # 2. RSI (Relative Strength Index) - 14 Periods
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))

        # 3. Bollinger Bands (20, 2)
        self.df['SMA_20'] = self.df['Close'].rolling(window=20).mean()
        self.df['BB_Std'] = self.df['Close'].rolling(window=20).std()
        self.df['BB_Upper'] = self.df['SMA_20'] + (self.df['BB_Std'] * 2)
        self.df['BB_Lower'] = self.df['SMA_20'] - (self.df['BB_Std'] * 2)

        # 4. MACD (12, 26, 9)
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD'] = ema12 - ema26
        self.df['MACD_Signal'] = self.df['MACD'].ewm(span=9, adjust=False).mean()

        # 5. ATR (Average True Range) - For Volatility & Stop Loss
        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['ATR'] = ranges.rolling(window=14).mean()
        
        # 6. ADX (Average Directional Index) - Nivo Filter
        plus_dm = self.df['High'].diff()
        minus_dm = self.df['Low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr = pd.concat([self.df['High'] - self.df['Low'],
                       (self.df['High'] - self.df['Close'].shift()).abs(),
                       (self.df['Low'] - self.df['Close'].shift()).abs()], axis=1).max(axis=1)
        
        atr_14 = tr.rolling(14).mean()
        # Add epsilon to avoid division by zero
        plus_di = 100 * (plus_dm.rolling(14).mean() / (atr_14 + 1e-9))
        minus_di = 100 * (abs(minus_dm.rolling(14).mean()) / (atr_14 + 1e-9))
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
        self.df['ADX'] = dx.rolling(14).mean()

    def analyze_market(self):
        """
        Analyzes the LAST available candle to generate a Score and a Signal.
        Optimized logic: Bidirectional (Buy/Sell) and weighted.
        """
        if len(self.df) < 200:
            return {"score": 0, "signal": "INSUFFICIENT DATA", "reasons": ["Need at least 200 bars"]}

        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        score_long = 0
        score_short = 0
        reasons_long = []
        reasons_short = []

        # --- LOGIC RULES (WEIGHTED SCORING) ---

        # 1. Macro Trend Filter (EMA 200) - 3.0 pts
        if last['Close'] > last['EMA_200']:
            score_long += 3.0
            reasons_long.append("✅ Above EMA 200 (Long Bias)")
        else:
            score_short += 3.0
            reasons_short.append("✅ Below EMA 200 (Short Bias)")

        # 2. RSI Momentum - 2.0 pts
        if last['RSI'] < 35:
            score_long += 2.0
            reasons_long.append("✅ RSI Oversold/Low")
        elif last['RSI'] > 65:
            score_short += 2.0
            reasons_short.append("✅ RSI Overbought/High")

        # 3. Bollinger Band Interactions - 2.0 pts
        if prev['Close'] < prev['BB_Lower'] and last['Close'] > last['BB_Lower']:
            score_long += 2.0
            reasons_long.append("✅ BB Lower Band Rejection (Bullish)")
        elif prev['Close'] > prev['BB_Upper'] and last['Close'] < prev['BB_Upper']:
            score_short += 2.0
            reasons_short.append("✅ BB Upper Band Rejection (Bearish)")

        # 4. MACD Crossover - 2.0 pts
        if prev['MACD'] < prev['MACD_Signal'] and last['MACD'] > last['MACD_Signal']:
            score_long += 2.0
            reasons_long.append("✅ MACD Bullish Crossover")
        elif prev['MACD'] > prev['MACD_Signal'] and last['MACD'] < prev['MACD_Signal']:
            score_short += 2.0
            reasons_short.append("✅ MACD Bearish Crossover")

        # 5. Volatility (ADX) - 1.0 pt
        if last['ADX'] > 25:
            if last['Close'] > last['EMA_200']: score_long += 1.0
            else: score_short += 1.0
            reasons_long.append("✅ Strong Trend Strength (ADX > 25)")
            reasons_short.append("✅ Strong Trend Strength (ADX > 25)")

        # --- 📈 PULLBACK (RETROCESO) LOGIC ---
        is_pullback = False
        pullback_type = None
        
        # Pullback en Tendencia Alcista (Long)
        if last['Close'] > last['EMA_200']:
            # El precio está en corrección si está cerca o debajo de EMA 50
            if last['Close'] <= last['EMA_50'] * 1.001: 
                # Gatillo: RSI saliendo de sobreventa o zona baja
                if last['RSI'] < 45:
                    is_pullback = True
                    pullback_type = "BULLISH PULLBACK"
                    score_long += 1.5 # Boost para favorecer la entrada en descuento
                    reasons_long.append("🎯 PULLBACK: Precio en descuento sobre EMA 50")
        
        # Pullback en Tendencia Bajista (Short)
        elif last['Close'] < last['EMA_200']:
            # El precio está en corrección (rally alcista temporal) si toca EMA 50
            if last['Close'] >= last['EMA_50'] * 0.999:
                # Gatillo: RSI en zona de sobrecompra relativa
                if last['RSI'] > 55:
                    is_pullback = True
                    pullback_type = "BEARISH PULLBACK"
                    score_short += 1.5
                    reasons_short.append("🎯 PULLBACK ESTRATÉGICO: Precio en zona de RECARGA (Short)")

        # Symmetrical Thresholds for Nivo Partners standard execution
        self.MIN_BUY = 60
        self.STRONG_BUY = 85
        self.MAX_SELL = 40
        self.STRONG_SELL = 15

        is_long = score_long > score_short  # STRICT: no long bias on tied scores → WAIT
        # Directional Score: 50 is neutral. 
        # If long, score goes from 50 to 100. If short, score goes from 50 to 0.
        if is_long:
            final_score = 50 + (score_long * 5) # Scale 0-10 to 50-100
        else:
            final_score = 50 - (score_short * 5) # Scale 0-10 to 50-0
            
        reasons = reasons_long if is_long else reasons_short
        
        signal = "WAIT"
        if final_score >= self.STRONG_BUY: 
            signal = "STRONG BUY"
        elif final_score >= self.MIN_BUY: 
            signal = "BUY"
        elif final_score <= self.STRONG_SELL: 
            signal = "STRONG SELL"
        elif final_score <= self.MAX_SELL: 
            signal = "SELL"
        
        return {
            "score": final_score,
            "signal": signal,
            "direction": "LONG" if is_long else "SHORT",
            "is_pullback": is_pullback,
            "pullback_type": pullback_type,
            "confidence": f"{final_score}%",
            "current_price": float(last['Close']),
            "stop_loss": float(last['Close'] - (1.5 * last['ATR'])) if is_long else float(last['Close'] + (1.5 * last['ATR'])),
            "take_profit": float(last['Close'] + (3.0 * last['ATR'])) if is_long else float(last['Close'] - (3.0 * last['ATR'])),
            "reasons": reasons
        }
