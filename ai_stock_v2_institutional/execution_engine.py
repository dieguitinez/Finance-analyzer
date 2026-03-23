import os
import logging
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class StockExecutionEngine:
    def __init__(self, trading_client):
        self.client = trading_client
        self.logger = logging.getLogger("StockSentinel")
        self.logger.info("[⚡ EXEC] Motor de Ejecución Alpaca (Nivo V2) inicializado.")

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
        self.logger.info(f"[EXEC] Intentando {side.value.upper()} {mode_str} de {symbol}...")
        if tp_price or sl_price:
            self.logger.info(f"[EXEC] Bracket: TP: {tp_price} | SL: {sl_price}")

        if qty is None and notional is None:
            self.logger.error("[EXEC] Error: Debes especificar qty o notional.")
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
            self.logger.info(f"[EXEC] ✅ Orden enviada! ID: {order.id}")
            return order

        except Exception as e:
            self.logger.error(f"[EXEC] ❌ Error en ejecución Alpaca: {e}")
            return None

    def get_buying_power(self):
        """Consulta el poder de compra disponible"""
        account = self.client.get_account()
        return float(account.buying_power)

    def has_open_position(self, symbol) -> bool:
        """
        Consulta si ya existe una posición abierta para el símbolo en Alpaca.
        Retorna True si hay posición, False si no la hay.
        """
        try:
            position = self.client.get_open_position(symbol_or_asset_id=symbol)
            return float(position.qty) != 0
        except Exception as e:
            if "position does not exist" in str(e).lower():
                return False
            self.logger.warning(f"[EXEC] ⚠️ Error checking open position for {symbol}: {e}")
            return True

    def has_pending_orders(self, symbol) -> bool:
        """
        Consulta si existen órdenes pendientes (Stop Loss / Take Profit) abiertas para el símbolo.
        """
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            orders = self.client.get_orders(req)
            return len(orders) > 0
        except Exception as e:
            self.logger.warning(f"[EXEC] ⚠️ Error checking pending orders for {symbol}: {e}")
            return False

    def place_oco_shield(self, symbol, tp_price, sl_price):
        """
        Coloca una orden OCO (Take Profit y Stop Loss) para una posición existente.
        """
        try:
            position = self.client.get_open_position(symbol_or_asset_id=symbol)
            qty = float(position.qty)
            
            from alpaca.trading.requests import LimitOrderRequest, StopLossRequest
            from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce

            # Determinar lado contrario para cerrar
            side = OrderSide.SELL if qty > 0 else OrderSide.BUY
            abs_qty = abs(qty)

            # Orden Limit principal (Take Profit) con Stop Loss adjunto (OCO)
            from alpaca.trading.requests import TakeProfitRequest
            
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=abs_qty,
                side=side,
                time_in_force=TimeInForce.GTC,
                limit_price=tp_price,
                order_class=OrderClass.OCO,
                take_profit=TakeProfitRequest(limit_price=tp_price),
                stop_loss=StopLossRequest(stop_price=sl_price)
            )
            order = self.client.submit_order(order_data=order_data)
            self.logger.info(f"[EXEC] 🛡️ Escudo OCO activado para {symbol}! Order ID: {order.id}")
            return order
        except Exception as e:
            self.logger.error(f"[EXEC] ❌ Error colocando escudo OCO para {symbol}: {e}")
            return None
