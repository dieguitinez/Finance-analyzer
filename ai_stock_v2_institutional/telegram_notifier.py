import os
import requests
from dotenv import load_dotenv

# Cargar .env desde el mismo directorio de este archivo (robusto en cualquier CWD)
_NOTIFIER_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_NOTIFIER_DIR, '.env'))

class StockTelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv('STOCK_TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('STOCK_TELEGRAM_CHAT_ID')
        self.enabled = all([self.bot_token, self.chat_id])
        
        if not self.enabled:
            print("⚠️ Telegram Notifier desactivado: Faltan llaves en .env")

    def send_raw_message(self, message: str, parse_mode: str = "HTML"):
        """Envía un mensaje directamente a Telegram."""
        if not self.enabled:
            return
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ Error enviando mensaje a Telegram: {e}")

    def send_alert(self, message: str):
        """Envía una alerta formateada a Telegram con link al Dashboard"""
        dashboard_url = "https://app.alpaca.markets/paper/dashboard"
        formatted_msg = f"{message}\n\n📊 <a href='{dashboard_url}'>Ver en Alpaca Dashboard</a>"
        self.send_raw_message(formatted_msg)

    # ─── TRADE NOTIFICATIONS (the only automated messages sent) ───────────────

    def send_trade_open(self, symbol: str, side: str, price: float, notional: float, reason: str):
        """
        Notificación de ENTRADA en una operación.
        Solo se envía cuando el bot ejecuta una orden en Alpaca.
        """
        icon = "🚀" if side == "BUY" else "🔻"
        side_label = "COMPRA" if side == "BUY" else "VENTA"
        dashboard_url = "https://app.alpaca.markets/paper/dashboard"
        msg = (
            f"{icon} <b>OPERACIÓN ABIERTA — {symbol}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Acción:</b> {side_label}\n"
            f"💵 <b>Precio entrada:</b> ${price:.2f}\n"
            f"💰 <b>Capital invertido:</b> ${notional:.2f}\n"
            f"🧠 <b>Motivo:</b> <i>{reason}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <a href='{dashboard_url}'>Ver en Alpaca</a>"
        )
        self.send_raw_message(msg)

    def send_trade_close(self, symbol: str, side: str, entry_price: float,
                         exit_price: float, qty: float, pnl_usd: float):
        """
        Notificación de SALIDA de una operación con P&L.
        Se envía cuando el bot detecta que una posición fue cerrada
        (por OCO, Stop Loss, Take Profit, o Panic).
        """
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0
        if side == "SELL":  # Short position: profit when price goes down
            pnl_pct = -pnl_pct

        is_profit = pnl_usd >= 0
        icon = "✅" if is_profit else "❌"
        result_label = "GANANCIA" if is_profit else "PÉRDIDA"
        dashboard_url = "https://app.alpaca.markets/paper/dashboard"

        msg = (
            f"{icon} <b>POSICIÓN CERRADA — {symbol}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Acciones:</b> {abs(qty):.4f}\n"
            f"📥 <b>Entrada:</b> ${entry_price:.2f}\n"
            f"📤 <b>Salida:</b> ${exit_price:.2f}\n"
            f"{'📈' if is_profit else '📉'} <b>{result_label}:</b> "
            f"${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <a href='{dashboard_url}'>Ver en Alpaca</a>"
        )
        self.send_raw_message(msg)

    def send_critical_alert(self, message: str):
        """
        Alerta de sistema crítica (sector bajista, kill switch, error grave).
        Usa el mismo canal pero sin link de dashboard para mayor urgencia.
        """
        self.send_raw_message(f"🚨 <b>ALERTA SISTEMA</b>\n\n{message}")


if __name__ == "__main__":
    # Test rápido de envío
    notifier = StockTelegramNotifier()
    if notifier.enabled:
        notifier.send_alert("🚀 *Test de Conexión:* Nivo Stock Sentinel Online.")
        print("✅ Mensaje de prueba enviado.")
    else:
        print("❌ No se pudo enviar el test (Configuración incompleta).")
