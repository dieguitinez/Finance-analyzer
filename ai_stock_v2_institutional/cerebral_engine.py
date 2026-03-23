import logging
import pandas as pd

class StockCerebralEngine:
    def __init__(self):
        self.logger = logging.getLogger("StockSentinel")
        self.logger.info("[🧠 CEREBRO] Motor Cerebral de Acciones (Nivo V2 Institutional) inicializado.")
        self.market_state = {} 

    def get_sector_strength(self, soxx_df, spy_df):
        """
        Calcula la fuerza relativa del sector semis vs mercado general.
        Strength Score = %SOXX_ret - %SPY_ret (Intradía)
        """
        if soxx_df is None or spy_df is None or len(soxx_df) < 2 or len(spy_df) < 2:
            return 0.0, "Neutral"
            
        soxx_ret = (soxx_df['close'].iloc[-1] / soxx_df['open'].iloc[0] - 1) * 100
        spy_ret = (spy_df['close'].iloc[-1] / spy_df['open'].iloc[0] - 1) * 100
        
        strength = soxx_ret - spy_ret
        
        label = "Liderazgo" if strength > 1.0 else "Estándar" if strength > 0 else "Debilidad"
        return strength, label

    def analyze_momentum(self, df, symbol="", sector_context=None):
        """
        Analiza si hay una 'Explosión de Momentum' con 'Huella de Ballena'.
        sector_context: dict con {'strength_score': float, 'leaders_bias': str}
        """
        df = df.copy() # Evitar SettingWithCopyWarning
        if len(df) < 50:
            return None, "Datos insuficientes"

        # 1. Indicadores Técnicos (NATIVOS PANDAS - Sin dependencias extra)
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # RSI Nativo
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
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
                return "BUY", "[LEADER] SECTOR LEADER (BULLISH): ASML rompiendo al alza con volumen masivo (>2.5x)."
            if is_bearish and is_massive_whale and is_not_oversold:
                return "SELL", "[LEADER] SECTOR LEADER (BEARISH): ASML rompiendo a la baja con volumen masivo (>2.5x)."

        # 5. MEAN REVERSION (Contrarian Buy / Panic Buying)
        # Institucional: Comprar pánico extremo justificado si la empresa es sólida.
        deviation_from_ema20 = ((ema_20 - current_price) / ema_20) * 100
        is_extreme_panic = current_rsi < 25 and deviation_from_ema20 > 3.0 # Más del 3% por debajo de la media móvil
        if is_extreme_panic and is_whale_present:
            return "BUY", f"[PANIC] MEAN REVERSION (CONTRARIAN BUY): Pánico extremo detectado. RSI: {current_rsi:.1f}, Desviación EMA20: -{deviation_from_ema20:.1f}%, Vol: {current_volume/avg_volume:.1f}x."

        # 6. Veredicto Final (Trend Following)
        if is_whale_present:
            # INTEGRACIÓN V2: Lead-Lag / Correlation Guard
            # Si el símbolo es un 'Seguidor' (ej: NVDA, SMCI), checar si los líderes (TSM, ASML)
            # ya se movieron o están en la misma dirección.
            force_score = 0
            if sector_context:
                strength = sector_context.get('strength_score', 0)
                leaders_bias = sector_context.get('leaders_bias', 'NEUTRAL')
                
                # VETO DE DEBILIDAD SECTORIAL
                if strength < -0.5 and is_bullish:
                    return None, f"[VETO] VETO SECTORIAL: {symbol} alcista pero sector (SOXX) débil vs mercado ({strength:.2f}%)."
                
                # BONO DE CONFIRMACIÓN DE LÍDERES
                if leaders_bias == "BULLISH" and is_bullish:
                    force_score += 1
                
            if is_bullish and is_not_overbought:
                confirmation = " CONFIRMADO POR LÍDERES" if force_score > 0 else ""
                return "BUY", f"[OK] TREND FOLLOWING{confirmation}: Volumen Institucional ({current_volume/avg_volume:.1f}x) y RSI sano ({current_rsi:.1f})."
            
            if is_bearish and is_not_oversold:
                # Nota: El watcher bloqueará esto si no tenemos posición (No Shorts)
                return "SELL", f"[WARN] TREND BREAK: Debilitamiento detectado con Volumen ({current_volume/avg_volume:.1f}x) y RSI ({current_rsi:.1f})."

            return None, f"[NEUTRAL] NEUTRAL: Riesgo extremo o falta de tendencia clara (RSI: {current_rsi:.1f}, Vol: {current_volume/avg_volume:.1f}x)."

        return None, f"[QUIET] NEUTRAL: Sin volumen institucional significativo ({current_volume/avg_volume:.1f}x)."
