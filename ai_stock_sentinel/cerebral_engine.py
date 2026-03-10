import pandas as pd
import pandas_ta as ta

class StockCerebralEngine:
    def __init__(self):
        print("🧠 Cerebro de Acciones (Nivo Engine) inicializado.")

    def analyze_momentum(self, df, symbol=""):
        """
        Analiza si hay una 'Explosión de Momentum' con 'Huella de Ballena'.
        Returns (signal, reason) where signal is 'BUY', 'SELL' or None.
        """
        if len(df) < 50:
            return None, "Datos insuficientes"

        # 1. Indicadores Técnicos
        df['ema_20'] = ta.ema(df['close'], length=20)
        df['ema_50'] = ta.ema(df['close'], length=50) # Macro short-term
        df['ema_200'] = ta.ema(df['close'], length=200) # Macro trend
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].tail(20).mean() # Ventana de volumen institucional

        # 2. Lógica de "Detector de Ballenas" (Whale Detector)
        # 1.5x es un spike institucional válido para scalps/swings cortos
        # 2.5x es pánico institucional puro
        is_whale_present = current_volume > (avg_volume * 1.5)
        is_massive_whale = current_volume > (avg_volume * 2.5)
        
        # 3. Lógica Direccional & Macro Trend Guard
        ema_20 = df['ema_20'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        ema_200 = df['ema_200'].iloc[-1]
        
        macro_bullish = ema_50 > ema_200
        price_above_50 = current_price > ema_50
        
        # BUY: Precio sobre EMA-20 Y (Tendencia macro a favor O recuperando EMA-50)
        is_bullish = current_price > ema_20 and (macro_bullish or price_above_50)
        
        # SELL: Precio bajo EMA-20 Y bajo EMA-50
        is_bearish = current_price < ema_20 and current_price < ema_50
        
        # Filtros RSI
        is_not_overbought = current_rsi < 68 
        is_not_oversold = current_rsi > 32

        # 4. Análisis Especial ASML (Indicador Adelantado)
        if symbol == "ASML":
            if is_bullish and is_massive_whale and is_not_overbought:
                return "BUY", "🏛️ SECTOR LEADER (BULLISH): ASML rompiendo al alza con volumen masivo (>2.5x)."
            if is_bearish and is_massive_whale and is_not_oversold:
                return "SELL", "🏛️ SECTOR LEADER (BEARISH): ASML rompiendo a la baja con volumen masivo (>2.5x)."

        # 5. MEAN REVERSION (Contrarian Buy / Panic Buying)
        # Institucional: Comprar pánico extremo justificado si la empresa es sólida.
        deviation_from_ema20 = ((ema_20 - current_price) / ema_20) * 100
        is_extreme_panic = current_rsi < 25 and deviation_from_ema20 > 3.0 # Más del 3% por debajo de la media móvil
        if is_extreme_panic and is_whale_present:
            return "BUY", f"🩸 MEAN REVERSION (CONTRARIAN BUY): Pánico extremo detectado. RSI: {current_rsi:.1f}, Desviación EMA20: -{deviation_from_ema20:.1f}%, Vol: {current_volume/avg_volume:.1f}x."

        # 6. Veredicto Final (Trend Following)
        if is_whale_present:
            if is_bullish and is_not_overbought:
                return "BUY", f"🐋 WHALE BUY: Momentum alcista. RSI {current_rsi:.1f}, Vol: {current_volume/avg_volume:.1f}x avg"
            if is_bearish and is_not_oversold:
                return "SELL", f"🐋 WHALE SELL: Momentum bajista. RSI {current_rsi:.1f}, Vol: {current_volume/avg_volume:.1f}x avg"
        
        return None, "Vigilancia normal (Sin huella institucional ni pánico)"
