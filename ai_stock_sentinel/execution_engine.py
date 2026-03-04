import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class StockExecutionEngine:
    def __init__(self, trading_client):
        self.client = trading_client
        print("⚡ Motor de Ejecución Alpaca (Nivo) inicializado.")

    def place_safe_order(self, symbol, qty=None, notional=None, side=OrderSide.BUY,
                         tp_price=None, sl_price=None):
        """
        Ejecuta una orden con Bracket (TP + SL).

        ✅ FIX: Soporta 'notional' (monto en USD) además de 'qty' (cantidad de acciones).
        Usar 'notional' es OBLIGATORIO para acciones de alto precio (ASML $700+, NVDA $130+)
        cuando operamos con $20/empresa, ya que 1 acción cuesta más que nuestro capital por trade.
        Ejemplo: notional=20.0 comprará $20 en acciones fraccionadas de NVDA automáticamente.

        Args:
            symbol:    Ticker (ej. 'NVDA')
            qty:       Cantidad de acciones (entero o fracción). Usar None si usas notional.
            notional:  Monto en USD (ej. 20.0). Alpaca comprará la fracción correcta.
            side:      OrderSide.BUY o OrderSide.SELL
            tp_price:  Precio de Take Profit
            sl_price:  Precio de Stop Loss
        """
        mode_str = f"${notional:.2f} notional" if notional else f"{qty} acciones"
        print(f"📡 Intentando {side.value.upper()} {mode_str} de {symbol}...")
        if tp_price or sl_price:
            print(f"🛡️ Bracket: TP: {tp_price} | SL: {sl_price}")

        if qty is None and notional is None:
            print("❌ Error: Debes especificar qty o notional.")
            return None

        try:
            from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

            tp_data = TakeProfitRequest(limit_price=tp_price) if tp_price else None
            sl_data = StopLossRequest(stop_price=sl_price) if sl_price else None

            # ✅ FIX: Construir la orden con notional O qty según lo que se pase
            order_params = dict(
                symbol=symbol,
                side=side,
                time_in_force=TimeInForce.DAY,
                take_profit=tp_data,
                stop_loss=sl_data
            )

            if notional is not None:
                # Notional: Alpaca divide por el precio actual y compra la fracción exacta
                order_params["notional"] = round(notional, 2)
            else:
                order_params["qty"] = qty

            order_data = MarketOrderRequest(**order_params)
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
