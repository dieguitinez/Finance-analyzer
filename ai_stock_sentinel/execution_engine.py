import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class StockExecutionEngine:
    def __init__(self, trading_client):
        self.client = trading_client
        print("⚡ Motor de Ejecución Alpaca (Nivo) inicializado.")

    def place_safe_order(self, symbol, qty, side=OrderSide.BUY, tp_price=None, sl_price=None):
        """
        Ejecuta una orden de mercado con una red de seguridad (Bracket Order: TP + SL).
        """
        print(f"📡 Intentando {side} de {qty} acciones de {symbol}...")
        if tp_price or sl_price:
            print(f"🛡️ Bracket: TP: {tp_price} | SL: {sl_price}")
        
        try:
            from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
            
            # Construir parámetros de TP/SL si existen
            tp_data = TakeProfitRequest(limit_price=tp_price) if tp_price else None
            sl_data = StopLossRequest(stop_price=sl_price) if sl_price else None

            # 1. Crear Orden de Mercado
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC, # Good Till Cancelled is better for brackets
                take_profit=tp_data,
                stop_loss=sl_data
            )
            
            # 2. Enviar Orden
            order = self.client.submit_order(order_data=order_data)
            print(f"✅ Orden enviada! ID: {order.id}")
            return order
            
        except Exception as e:
            print(f"❌ Error en ejecución Alpaca: {e}")
            return None

    def get_buying_power(self):
        """Consulta el poder de compra disponible"""
        account = self.client.get_account()
        return float(account.buying_power)
