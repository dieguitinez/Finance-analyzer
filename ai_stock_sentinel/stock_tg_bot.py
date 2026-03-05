import os
import time
import requests
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Stock Engine Imports
from cerebral_engine import StockCerebralEngine
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.historical import StockHistoricalDataClient

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

        # Engine
        self.cerebro = StockCerebralEngine()
        self.watchlist = os.getenv('STOCK_WATCHLIST', 'NVDA,TSM').split(',')

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
                self.data_client = StockHistoricalDataClient(api_key, secret_key)
                logger.info("✅ Alpaca client connected")
            else:
                self.trading_client = None
                self.data_client = None
                logger.warning("⚠️ ALPACA_API_KEY missing — /status and /saldo disabled")
        except Exception as e:
            self.trading_client = None
            self.data_client = None
            logger.error(f"⚠️ Alpaca init failed: {e}")

    def send_message(self, text, reply_markup=None):
        url     = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
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
                "🔹 /analizar - 🧠 Análisis IA instantáneo de un activo\n"
                "🔹 /status - Posiciones abiertas en Alpaca\n"
                "🔹 /saldo - Balance y poder de compra\n"
                "🔹 /kill - 🛑 Cerrar TODAS las posiciones (emergencia)\n"
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

        elif command == "/analizar":
            keyboard = []
            row = []
            for i, sym in enumerate(self.watchlist):
                row.append({"text": sym.strip(), "callback_data": f"analyze_{sym.strip()}"})
                if len(row) == 3 or i == len(self.watchlist) - 1:
                    keyboard.append(row)
                    row = []
            
            reply_markup = {"inline_keyboard": keyboard}
            self.send_message(
                "🧠 <b>Selecciona la acción a analizar:</b>",
                reply_markup=reply_markup
            )

        elif command == "/kill":
            if not self.trading_client:
                self.send_message("❌ Alpaca API no configurada. Verifica ALPACA_API_KEY en .env")
                return
            try:
                positions = self.trading_client.get_all_positions()
                if not positions:
                    self.send_message("ℹ️ No hay posiciones abiertas para cerrar.")
                    return
                n = len(positions)
                self.trading_client.close_all_positions(cancel_orders=True)
                self.send_message(
                    f"🛑 <b>KILL SWITCH EJECUTADO</b>\n"
                    f"Cerrando {n} posición(es) en Alpaca Paper.\n"
                    f"Verifica en /status en ~30s."
                )
            except Exception as e:
                self.send_message(f"❌ Error al ejecutar kill switch: {e}")

        else:
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /ayuda.")

    def _handle_callback_query(self, query):
        data = query.get("data", "")
        sender_id = str(query.get("message", {}).get("chat", {}).get("id"))
        
        if self.chat_id and sender_id != self.chat_id:
            return  # Unauthorized

        if data.startswith("analyze_"):
            symbol = data.split("_")[1]
            self.send_message(f"⏳ <i>Descargando datos y analizando {symbol}...</i>")
            
            if not getattr(self, "data_client", None):
                self.send_message("❌ Alpaca API no está configurada para obtener datos.")
                return
                
            try:
                # 1. Bajar data
                start_time = datetime.now() - timedelta(days=5)
                request_params = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Minute,
                    start=start_time
                )
                bars = self.data_client.get_stock_bars(request_params)
                df = bars.df
                
                # 2. Correr cerebro
                signal, reason = self.cerebro.analyze_momentum(df, symbol)
                current_price = df['close'].iloc[-1]
                
                # 3. Formatear output
                if not signal:
                    icon = "💤"
                    status = "NEUTRAL"
                    rec = "Mantener vigilancia normal."
                else:
                    icon = "🚀" if signal == "BUY" else "🔻"
                    status = signal
                    rec = "Oportunidad detectada (Revisar logs para ejecución)."

                msg = (
                    f"🧠 <b>Análisis IA: {symbol}</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 <b>Precio Actual:</b> ${current_price:.2f}\n"
                    f"{icon} <b>Veredicto:</b> {status}\n\n"
                    f"📝 <b>Detalle del Motor Nivo:</b>\n"
                    f"<i>{reason}</i>\n\n"
                    f"💡 <b>Recomendación:</b> {rec}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
                self.send_message(msg)
                
            except Exception as e:
                self.send_message(f"❌ <b>Error analizando {symbol}:</b>\n<code>{e}</code>")

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
                            
                    elif "callback_query" in update:
                        # Handle inline button clicks
                        self._handle_callback_query(update["callback_query"])
                        
                        # Answer callback query to remove loading state on button
                        cb_id = update["callback_query"].get("id")
                        if cb_id:
                            cb_url = f"{self.api_url}/answerCallbackQuery"
                            requests.post(cb_url, json={"callback_query_id": cb_id}, timeout=5)
                            
            else:
                logger.error(f"Polling error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error polling: {e}")

    def _clear_stale_session(self):
        """
        Two-step Telegram session takeover:
        1. deleteWebhook — clears any registered webhook
        2. getUpdates(timeout=0) — steals back the polling slot from any
           other active instance. Telegram only allows ONE active getUpdates
           session per token; calling it with timeout=0 immediately terminates
           the previous one and hands control to us.
        """
        try:
            requests.post(
                f"{self.api_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10
            )
        except Exception:
            pass

        # Force-close any active long-poll session held by a previous process
        try:
            resp = requests.get(
                f"{self.api_url}/getUpdates",
                params={"timeout": 0, "offset": -1},
                timeout=10
            )
            if resp.status_code == 200:
                logger.info("✅ Telegram poll slot acquired (stale session cleared).")
            else:
                logger.warning(f"⚠️ getUpdates(timeout=0) returned {resp.status_code}.")
        except Exception as e:
            logger.warning(f"⚠️ Could not steal poll slot: {e}")

    def run(self):
        logger.info("🚀 Stock Telegram Bot started.")
        logger.info(f"   Authorized chat_id: {self.chat_id or '(NOT SET)'}")
        # Clear any stale Telegram long-poll session from previous instance (prevents 409)
        self._clear_stale_session()
        self.send_message("🤖 <b>Stock Sentinel Online.</b> /ayuda para comandos.")
        while True:
            self.poll_updates()
            time.sleep(1)


if __name__ == "__main__":
    bot = NivoStockBot()
    bot.run()
