import os
import time
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler

try:
    from telegram_notifier import StockTelegramNotifier
    from cerebral_engine import StockCerebralEngine
    from execution_engine import StockExecutionEngine
except ImportError:
    from ai_stock_sentinel.telegram_notifier import StockTelegramNotifier
    from ai_stock_sentinel.cerebral_engine import StockCerebralEngine
    from ai_stock_sentinel.execution_engine import StockExecutionEngine

# Cargar configuración aislada
load_dotenv('ai_stock_sentinel/.env')

class NivoStockWatcher:
    def __init__(self):
        # 🛡️ Configuración de Logs (Rotación Automática para evitar llenar el disco)
        log_file = 'ai_stock_sentinel/sentinel.log'
        self.logger = logging.getLogger("StockSentinel")
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.is_paper = os.getenv('ALPACA_PAPER', 'True') == 'True'
        
        # Clientes de Alpaca
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=self.is_paper)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        
        # Motores Nivo
        self.notifier = StockTelegramNotifier()
        self.cerebro = StockCerebralEngine()
        self.executor = StockExecutionEngine(self.trading_client)
        
        self.watchlist = os.getenv('STOCK_WATCHLIST', 'NVDA,TSM').split(',')
        self.autonomous_mode = os.getenv('STOCK_AUTONOMOUS_MODE', 'True') == 'True'
        
        self.logger.info(f"🚀 Nivo AI Stock Sentinel iniciado.")
        self.logger.info(f"📡 Monitoreando {len(self.watchlist)} activos de IA: {self.watchlist}")
        self.logger.info(f"🤖 Modo Autónomo: {'ACTIVADO' if self.autonomous_mode else 'DESACTIVADO (Solo Alertas)'}")
        self.last_prices = {}

    def get_historical_data(self, symbol):
        """Obtiene velas recientes para análisis técnico"""
        start_time = datetime.now() - timedelta(days=5)
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_time
        )
        bars = self.data_client.get_stock_bars(request_params)
        return bars.df

    def scan_market(self):
        """Escanea y ejecuta con lógica de Convicción de Sector"""
        print(f"\n🔍 Escaneo de Alta Inteligencia: {time.strftime('%H:%M:%S')}")
        
        # 1. Analizar primero al Líder (ASML) como Indicador Adelantado
        sector_conviction = False
        try:
            asml_df = self.get_historical_data("ASML")
            asml_signal, _ = self.cerebro.analyze_momentum(asml_df, "ASML")
            if asml_signal:
                sector_conviction = True
                self.logger.info("🏛️ ALTA CONVICCIÓN: ASML está liderando el sector hoy.")
        except Exception as e:
            self.logger.error(f"⚠️ Error analizando líder ASML: {e}")

        # 2. Analizar el resto de la Watchlist
        for symbol in self.watchlist:
            try:
                df = self.get_historical_data(symbol)
                signal, reason = self.cerebro.analyze_momentum(df, symbol)
                current_price = df['close'].iloc[-1]
                
                print(f"💎 {symbol}: ${current_price:.2f} | {reason}")
                
                # 3. Ejecución con Filtro de Convicción
                if signal:
                    # Si ASML también está fuerte (o si es ASML mismo), la señal es más potente
                    is_high_conviction = sector_conviction or symbol == "ASML"
                    
                    msg = f"🚀 *Nivo Sentinel:* Señal detectada en {symbol}\nMotivo: {reason}"
                    if is_high_conviction:
                        msg = f"🏛️ *SECTOR CONVICTION ALERT*\n{msg}"

                    if self.autonomous_mode:
                        self.notifier.send_alert(f"{msg}\n✅ *Ejecutando orden...*")
                        self.executor.place_safe_order(symbol, qty=1)
                    else:
                        self.notifier.send_alert(f"{msg}\n⚠️ *Esperando validación.*")
                        print(f"📡 Señal en {symbol} - Omitida (Modo Manual).")
                    
            except Exception as e:
                print(f"❌ Error analizando {symbol}: {e}")

    def run(self):
        """Bucle principal de vigilancia"""
        try:
            while True:
                self.scan_market()
                print("-" * 30)
                time.sleep(60) # Escaneo por minuto
        except KeyboardInterrupt:
            print("\n🛑 Vigilancia detenida por el usuario.")

if __name__ == "__main__":
    watcher = NivoStockWatcher()
    watcher.run()
