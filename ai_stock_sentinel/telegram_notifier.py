import os
import requests
from dotenv import load_dotenv

# Cargar configuración aislada
load_dotenv('ai_stock_sentinel/.env')

class StockTelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv('STOCK_TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('STOCK_TELEGRAM_CHAT_ID')
        self.enabled = all([self.bot_token, self.chat_id])
        
        if not self.enabled:
            print("⚠️ Telegram Notifier desactivado: Faltan llaves en .env")

    def send_alert(self, message: str):
        """Envía una alerta formateada a Telegram"""
        if not self.enabled:
            return
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"❌ Error enviando a Telegram: {response.text}")
        except Exception as e:
            print(f"❌ Fallo de conexión con Telegram: {e}")

    def notify_market_scan(self, symbol, price, change=None):
        """Notifica un movimiento interesante"""
        emoji = "📈" if (change and change > 0) else "📉"
        msg = (
            f"*Nivo Stock Alert* {emoji}\n\n"
            f"🔹 *Activo:* {symbol}\n"
            f"💵 *Precio:* ${price:.2f}\n"
        )
        if change:
            msg += f"📊 *Cambio:* {change:+.2f}%\n"
            
        msg += f"\n_Monitoreo Institucional Nivo Partners_"
        self.send_alert(msg)

if __name__ == "__main__":
    # Test rápido de envío
    notifier = StockTelegramNotifier()
    if notifier.enabled:
        notifier.send_alert("🚀 *Test de Conexión:* Nivo Stock Sentinel Online.")
        print("✅ Mensaje de prueba enviado.")
    else:
        print("❌ No se pudo enviar el test (Configuración incompleta).")
