import os
import time
import requests
import logging
from dotenv import load_dotenv

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
        load_dotenv(env_path, override=True)

        self.token    = os.getenv("STOCK_TELEGRAM_BOT_TOKEN")
        self.chat_id  = str(os.getenv("STOCK_TELEGRAM_CHAT_ID", "")).strip()
        self.api_url  = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0

        if not self.token or not self.chat_id:
            logger.error("❌ STOCK_TELEGRAM_BOT_TOKEN or STOCK_TELEGRAM_CHAT_ID missing in ai_stock_sentinel/.env")

        # Alpaca (optional — only needed for /status and /saldo)
        self._init_alpaca()

    def _init_alpaca(self):
        """Initialize Alpaca client safely. Bot still works without it for info commands."""
        try:
            from alpaca.trading.client import TradingClient
            api_key    = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            is_paper   = os.getenv("ALPACA_PAPER", "True") == "True"
            if api_key and secret_key:
                self.trading_client = TradingClient(api_key, secret_key, paper=is_paper)
                logger.info("✅ Alpaca client connected")
            else:
                self.trading_client = None
                logger.warning("⚠️ ALPACA_API_KEY missing — /status and /saldo disabled")
        except Exception as e:
            self.trading_client = None
            logger.error(f"⚠️ Alpaca init failed: {e}")

    def send_message(self, text):
        url     = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def handle_command(self, command, args=[], sender_id=""):
        command = command.lower().split("@")[0]  # Handle /cmd@botname format
        dashboard_url = "https://app.alpaca.markets/paper/dashboard"

        if command in ["/start", "/help", "/ayuda"]:
            help_text = (
                "🤖 <b>Nivo Stock Sentinel - Command Center</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Comandos disponibles:\n"
                "🔹 /status - Posiciones abiertas en Alpaca\n"
                "🔹 /saldo - Balance y poder de compra\n"
                "🔹 /watchlist - Las 15 acciones vigiladas\n"
                "🔹 /dashboard - Link a Alpaca Dashboard\n"
                "🔹 /chatid - Ver tu Chat ID (para configuración)\n"
                "🔹 /ayuda - Este mensaje\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <a href='{dashboard_url}'>Alpaca Web Console</a>\n\n"
                "<i>Nivo Partners Stock Intelligence</i>"
            )
            self.send_message(help_text)

        elif command == "/chatid":
            # Diagnostic: tells user their exact chat ID so they can configure .env
            self.send_message(
                f"🔍 <b>Tu Chat ID:</b> <code>{sender_id}</code>\n\n"
                f"El bot está configurado para: <code>{self.chat_id}</code>\n\n"
                "Si son diferentes, actualiza <b>STOCK_TELEGRAM_CHAT_ID</b> en "
                "<code>ai_stock_sentinel/.env</code> con tu Chat ID."
            )

        elif command == "/dashboard":
            self.send_message(f"📊 <b>Alpaca Web Dashboard:</b>\n{dashboard_url}")

        elif command == "/saldo":
            if not self.trading_client:
                self.send_message("❌ Alpaca API no configurada. Verifica ALPACA_API_KEY en .env")
                return
            try:
                account = self.trading_client.get_account()
                pnl     = float(account.equity) - float(account.last_equity)
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                msg = (
                    "💰 <b>Estado de Cuenta Alpaca (Paper):</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 <b>Equity:</b> ${float(account.equity):,.2f}\n"
                    f"💎 <b>Buying Power:</b> ${float(account.buying_power):,.2f}\n"
                    f"{pnl_emoji} <b>PnL Hoy:</b> ${pnl:+,.2f}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al consultar saldo: {e}")

        elif command == "/status":
            if not self.trading_client:
                self.send_message("❌ Alpaca API no configurada.")
                return
            try:
                positions = self.trading_client.get_all_positions()
                if not positions:
                    self.send_message("✅ <b>Portfolio Limpio.</b> No hay acciones en cartera.")
                    return
                msg = "📝 <b>Posiciones Abiertas:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for pos in positions:
                    side    = "🟢" if float(pos.qty) > 0 else "🔴"
                    pnl_pct = float(pos.unrealized_plpc) * 100
                    msg    += f"{side} <b>{pos.symbol}</b>: {pos.qty} acciones | {pnl_pct:+.2f}%\n"
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
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /ayuda.")

    def poll_updates(self):
        url    = f"{self.api_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text      = update["message"]["text"]
                        sender_id = str(update["message"]["chat"]["id"])

                        # ─── Authorization check ────────────────────────────────
                        if self.chat_id and sender_id != self.chat_id:
                            logger.warning(
                                f"⚠️ Unauthorized from chat_id={sender_id} "
                                f"(configured={self.chat_id}). "
                                f"Update ai_stock_sentinel/.env if this is you."
                            )
                            # Still respond to /chatid so user can self-diagnose
                            if text.strip().startswith("/chatid"):
                                self.handle_command("/chatid", sender_id=sender_id)
                            continue

                        if text.startswith("/"):
                            parts = text.split()
                            self.handle_command(parts[0], parts[1:], sender_id=sender_id)
            else:
                logger.error(f"Polling error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error polling: {e}")

    def run(self):
        logger.info("🚀 Stock Telegram Bot started.")
        logger.info(f"   Authorized chat_id: {self.chat_id or '(NOT SET)'}")
        self.send_message("🤖 <b>Stock Sentinel Online.</b> /ayuda para comandos.")
        while True:
            self.poll_updates()
            time.sleep(1)


if __name__ == "__main__":
    bot = NivoStockBot()
    bot.run()
