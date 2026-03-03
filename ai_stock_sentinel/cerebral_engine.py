import pandas as pd
import pandas_ta as ta

class StockCerebralEngine:
    def __init__(self):
        print("🧠 Cerebro de Acciones (Nivo Engine) inicializado.")

    def analyze_momentum(self, df, symbol=""):
        """
        Analiza si hay una 'Explosión de Momentum' con 'Huella de Ballena'.
        """
        if len(df) < 50:
            return False, "Datos insuficientes"

        # 1. Indicadores Técnicos
        df['ema_20'] = ta.ema(df['close'], length=20)
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].tail(20).mean() # Ventana de volumen institucional

        # 2. Lógica de "Detector de Ballenas" (Whale Detector)
        # Solo entramos si el volumen es al menos 2.5x el promedio reciente
        is_whale_present = current_volume > (avg_volume * 2.5)
        
        # 3. Lógica de "Hemisferio Izquierdo"
        is_bullish = current_price > df['ema_20'].iloc[-1]
        is_not_overbought = current_rsi < 68 # Un poco más conservativo (Institucional)

        # 4. Análisis Especial ASML (Indicador Adelantado)
        if symbol == "ASML":
            if is_bullish and is_whale_present:
                return True, "🏛️ SECTOR LEADER SIGNAL: ASML subiendo con volumen masivo. Posible movimiento en cadena."

        # 5. Veredicto Final
        if is_bullish and is_whale_present and is_not_overbought:
            return True, f"🐋 WHALE DETECTED: RSI {current_rsi:.1f}, Vol: {current_volume/avg_volume:.1f}x avg"
        
        return False, "Vigilancia normal (Sin huella institucional)"
