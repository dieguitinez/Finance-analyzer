import os
import time
import requests
import logging
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderStatus

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | STOCK BOT: [%(levelname)s] | %(message)s'
)
logger = logging.getLogger(__name__)

class NivoStockBot:
    def __init__(self):
        # Load from specific Stock Sentinel .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path)
        
        self.token = os.getenv("STOCK_TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("STOCK_TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        
        # Alpaca Setup
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.is_paper = os.getenv("ALPACA_PAPER", "True") == "True"
        
        if self.api_key and self.secret_key:
            self.trading_client = TradingClient(self.api_key, self.secret_key, paper=self.is_paper)
        else:
            self.trading_client = None
            logger.error("Alpaca API keys not found in .env")

    def send_message(self, text):
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def handle_command(self, command, args=[]):
        command = command.lower()
        
        if command in ["/start", "/help", "/ayuda"]:
            help_text = (
                "🤖 <b>Nivo Stock Sentinel - Command Center</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Comandos disponibles:\n"
                "🔹 /status - Ver posiciones abiertas en Alpaca\n"
                "🔹 /saldo - Balance y poder de compra\n"
                "🔹 /watchlist - Ver las 15 acciones vigiladas\n"
                "🔹 /ayuda - Mostrar este mensaje\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Nivo Partners Stock Intelligence</i>"
            )
            self.send_message(help_text)

        elif command == "/saldo":
            if not self.trading_client:
                self.send_message("❌ Error: Alpaca API no configurada.")
                return
            try:
                account = self.trading_client.get_account()
                msg = (
                    "💰 <b>Estado de Cuenta Alpaca:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 <b>Equity:</b> ${float(account.equity):,.2f}\n"
                    f"💎 <b>Buying Power:</b> ${float(account.buying_power):,.2f}\n"
                    f"📈 <b>PnL Diario:</b> ${float(account.equity) - float(account.last_equity):,.2f}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al consultar saldo: {e}")

        elif command == "/status":
            if not self.trading_client:
                self.send_message("❌ Error: Alpaca API no configurada.")
                return
            try:
                positions = self.trading_client.get_all_positions()
                if not positions:
                    self.send_message("✅ <b>Portafolio Limpio.</b> No hay acciones en cartera.")
                    return
                
                msg = "📝 <b>Posiciones Abiertas:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for pos in positions:
                    side = "🟢" if float(pos.qty) > 0 else "🔴"
                    pnl_pct = float(pos.unrealized_plpc) * 100
                    msg += f"{side} <b>{pos.symbol}</b>: {pos.qty} acciones | {pnl_pct:+.2f}%\n"
                msg += "━━━━━━━━━━━━━━━━━━━━"
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al listar posiciones: {e}")

        elif command == "/watchlist":
            watchlist = os.getenv("STOCK_WATCHLIST", "No definido")
            msg = (
                "📡 <b>Vigilancia Activa (AI Core):</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{watchlist}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Escaneando 'Whale Spikes' y Momentum cada 60s."
            )
            self.send_message(msg)

        else:
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /ayuda para ver los disponibles.")

    def poll_updates(self):
        url = f"{self.api_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"]
                        user_id = str(update["message"]["chat"]["id"])
                        if user_id != self.chat_id:
                            logger.warning(f"Unauthorized access from {user_id}")
                            continue
                        if text.startswith("/"):
                            parts = text.split()
                            self.handle_command(parts[0], parts[1:])
            else:
                logger.error(f"Polling error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error polling: {e}")

    def run(self):
        logger.info("Stock Telegram Bot started.")
        self.send_message("🤖 <b>Stock Sentinel Online.</b> /ayuda para comandos.")
        while True:
            self.poll_updates()
            time.sleep(1)

if __name__ == "__main__":
    bot = NivoStockBot()
    bot.run()
