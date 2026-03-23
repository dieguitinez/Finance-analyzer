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
        self.callback_cooldowns = {} # Rate limiting

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

    def delete_message(self, message_id):
        url = f"{self.api_url}/deleteMessage"
        payload = {"chat_id": self.chat_id, "message_id": message_id}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")

    def handle_command(self, command, args=[], sender_id=""):
        command = command.lower().split("@")[0]  # Handle /cmd@botname format
        dashboard_url = "https://app.alpaca.markets/paper/dashboard"

        if command in ["/start", "/help", "/ayuda"]:
            help_text = (
                "🤖 <b>Nivo Stock Sentinel - Command Center</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Comandos principales:\n"
                "🔹 /status - Vista rápida de cartera\n"
                "🔹 /detalles - 🔎 Entry, TP/SL y PnL detallado\n"
                "🔹 /logica - 🧠 Explicación de mi estrategia\n"
                "🔹 /analizar - Análisis IA instantáneo\n"
                "🔹 /saldo - Balance y poder de compra\n"
                "🔹 /kill (🛑 PANIC) - Cerrar todo\n"
                "🔹 /ayuda - Este mensaje\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <a href='{dashboard_url}'>Alpaca Web Console</a>\n\n"
                "<i>Nivo Partners Stock Intelligence</i>"
            )
            keyboard_markup = {
                "keyboard": [
                    [{"text": "/status"}, {"text": "/detalles"}],
                    [{"text": "/analizar"}, {"text": "/logica"}],
                    [{"text": "/watchlist"}, {"text": "/saldo"}],
                    [{"text": "🛑 PANIC"}, {"text": "▶️ RESUME"}]
                ],
                "resize_keyboard": True,
                "is_persistent": True
            }
            self.send_message(help_text, reply_markup=keyboard_markup)


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
                    
                msg = "📝 <b>Estado de Cartera:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for pos in positions:
                    side    = "🟢" if float(pos.qty) > 0 else "🔴"
                    pnl_pct = float(pos.unrealized_plpc) * 100
                    pnl_usd = float(pos.unrealized_intraday_pl)
                    
                    msg += f"{side} <b>{pos.symbol}</b>: {pos.qty} acc | {pnl_pct:+.2f}% (${pnl_usd:+.2f})\n"
                msg += "━━━━━━━━━━━━━━━━━━━━\n<i>Usa /detalles para ver precios de entrada y objetivos.</i>"
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al listar posiciones: {e}")

        elif command == "/detalles":
            if not self.trading_client:
                self.send_message("❌ Alpaca API no configurada.")
                return
            try:
                positions = self.trading_client.get_all_positions()
                if not positions:
                    self.send_message("✅ No hay posiciones abiertas para detallar.")
                    return

                # Cargar el tracker para targets
                pdt_tracker = {}
                pdt_file = "/tmp/nivo_stock_pdt_tracker.json"
                if os.path.exists(pdt_file):
                    import json
                    with open(pdt_file, "r") as f:
                        pdt_tracker = json.load(f)

                msg = "🔎 <b>Detalles de Operaciones Active:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for pos in positions:
                    symbol = pos.symbol
                    data = pdt_tracker.get(symbol, {})
                    
                    # Si data es solo un string (formato viejo), lo manejamos
                    if isinstance(data, str):
                        data = {"date": data}
                    
                    entry = data.get("entry_price", float(pos.avg_entry_price))
                    tp    = data.get("tp_target", "N/A")
                    sl    = data.get("sl_target", "N/A")
                    c_date = data.get("date", "Desconocida")
                    
                    curr_price = float(pos.current_price)
                    pnl_pct = float(pos.unrealized_plpc) * 100
                    
                    msg += (
                        f"🔹 <b>{symbol}</b> (Desde {c_date})\n"
                        f" • Entrada: ${entry:,.2f}\n"
                        f" • Actual: ${curr_price:,.2f} ({pnl_pct:+.2f}%)\n"
                        f" • 🎯 TakeProfit: <code>{tp}</code>\n"
                        f" • 🛡️ StopLoss: <code>{sl}</code>\n\n"
                    )
                msg += "━━━━━━━━━━━━━━━━━━━━"
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al obtener detalles: {e}")

        elif command == "/logica":
            logic_msg = (
                "🧠 <b>Lógica de Trading: Nivo Stock Sentinel</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Mi algoritmo opera bajo un flujo híbrido:\n\n"
                "1️⃣ <b>Filtro de Sector (SOXX/QQQ):</b>\n"
                "Normalmente bloqueo compras si los semiconductores bajan >3% para proteger el capital.\n\n"
                "2️⃣ <b>Estrategia 'Maestro':</b>\n"
                "Si una acción individual muestra <b>Relative Strength</b> (sube mientras el sector baja) o detecto un <b>'Massive Whale'</b> (volumen institucional x3), ignoro el veto de sector y ejecuto la compra.\n\n"
                "3️⃣ <b>Protección PDT (Pattern Day Trader):</b>\n"
                "Bajo ninguna circunstancia vendo una acción el mismo día que la compro (Day 1), evitando penalizaciones del broker. Las salidas se gestionan del Día 2 en adelante.\n\n"
                "4️⃣ <b>Salidas (Día 2+):</b>\n"
                "Busco un +5% de beneficio (TP) o corto pérdidas en -2% (SL) mediante el OCO Shield.\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            self.send_message(logic_msg)

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

        elif command in ["/kill", "/panic", "🛑 panic"]:
            if not getattr(self, "trading_client", None):
                self.send_message("❌ Alpaca API no configurada. Verifica ALPACA_API_KEY en .env")
                return
            
            keyboard = [
                [{"text": "⚠️ SÍ, EJECUTAR PÁNICO", "callback_data": "panic_confirm"}],
                [{"text": "❌ CANCELAR", "callback_data": "panic_cancel"}]
            ]
            reply_markup = {"inline_keyboard": keyboard}
            self.send_message(
                "🚨 <b>¿ESTÁS COMPLETAMENTE SEGURO?</b>\n\n"
                "Esta acción:\n"
                "1. Cerrará todas tus posiciones maduras (Día 2+) a precio de mercado.\n"
                "2. Congelará el bot (detendrá nuevas compras).\n\n"
                "<i>Las posiciones de hoy se mantendrán abiertas para protegerte de penalizaciones PDT.</i>\n\n"
                "<b>¿Proceder con la emergencia?</b>",
                reply_markup=reply_markup
            )

        elif command in ["/resume", "▶️ resume"]:
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                panic_lock_path = os.path.join(project_root, ".panic_lock")
                if os.path.exists(panic_lock_path):
                    os.remove(panic_lock_path)
                    self.send_message("✅ <b>SISTEMA REANUDADO</b>\nEl scanner de Alpaca vuelve a estar operativo.")
                else:
                    self.send_message("ℹ️ El sistema ya estaba operativo.")
            except Exception as e:
                self.send_message(f"❌ Error al reanudar: {e}")

        else:
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /ayuda.")

    def _execute_panic(self):
        try:
            # Create .panic_lock to stop the watcher
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            panic_lock_path = os.path.join(project_root, ".panic_lock")
            with open(panic_lock_path, "w") as f:
                f.write("LOCKED")

            positions = self.trading_client.get_all_positions()
            if not positions:
                self.send_message("🛑 <b>PANIC SWITCH ACTIVO</b>\nNo hay posiciones, pero el scanner ha sido detenido.")
                return

            # Read PDT tracker to protect Day-1 positions
            pdt_tracker = {}
            try:
                import json
                pdt_file = "/tmp/nivo_stock_pdt_tracker.json"
                if os.path.exists(pdt_file):
                    with open(pdt_file, "r") as f:
                        pdt_tracker = json.load(f)
            except Exception as e:
                logger.error(f"Error reading PDT tracker for Panic: {e}")

            from datetime import date
            today = date.today()
            
            closed = 0
            kept = 0
            kept_symbols = []

            for pos in positions:
                try:
                    # Siempre cancelar órdenes pendientes (Limit/Stop) para evitar compras accidentales
                    self.trading_client.cancel_orders(symbol_or_asset_id=pos.symbol)
                except Exception:
                    pass
                    
                purchase_date_str = pdt_tracker.get(pos.symbol)
                is_safe = True
                
                if purchase_date_str:
                    try:
                        purchase_date = date.fromisoformat(purchase_date_str)
                        if purchase_date >= today:
                            # Comprado HOY - Consultar contador de Day Trades local (strict simulation)
                            try:
                                dt_history = pdt_tracker.get("__dt_history__", [])
                                from datetime import timedelta
                                
                                business_days_counted = 0
                                start_date = today
                                while business_days_counted < 5:
                                    if start_date.weekday() < 5:  # 0=Lun, ..., 4=Vie
                                        business_days_counted += 1
                                    start_date -= timedelta(days=1)
                                    
                                recent_dts = [d for d in dt_history if date.fromisoformat(d) > start_date]
                                
                                dt_count = len(recent_dts)
                                if dt_count >= 3:
                                    is_safe = False # Bloqueado, reached PDT limit local
                            except Exception as e:
                                logger.error(f"Error checking local daytrade history in panic: {e}")
                                is_safe = False # Falla segura (bloquear)
                    except Exception:
                        pass
                        
                if is_safe:
                    self.trading_client.close_position(symbol_or_asset_id=pos.symbol)
                    closed += 1
                    
                    # Registrar el gasto de token PDT si se compró hoy
                    if purchase_date_str:
                        try:
                            if date.fromisoformat(purchase_date_str) == today:
                                dt_history = pdt_tracker.get("__dt_history__", [])
                                dt_history.append(today.isoformat())
                                pdt_tracker["__dt_history__"] = dt_history
                                import json
                                with open("/tmp/nivo_stock_pdt_tracker.json", "w") as f:
                                    json.dump(pdt_tracker, f)
                        except Exception as e:
                            logger.error(f"Error guardando token PDT post-panic para {pos.symbol}: {e}")

                else:
                    kept += 1
                    kept_symbols.append(pos.symbol)

            msg = (
                f"🛑 <b>PANIC SWITCH EJECUTADO</b>\n"
                f"Cerrando {closed} posición(es) maduras (Día 2+).\n"
                f"Scanner detenido via .panic_lock."
            )
            if kept > 0:
                symbols_str = ", ".join(kept_symbols)
                msg += f"\n\n🛡️ <b>Protección PDT:</b> Se mantuvieron {kept} posiciones abiertas ({symbols_str}) porque fueron compradas HOY. Se cerrarán a partir de mañana."

            self.send_message(msg)
        except Exception as e:
            self.send_message(f"❌ Error al ejecutar panic switch: {e}")

    def _handle_callback_query(self, query):
        data = query.get("data", "")
        sender_id = str(query.get("message", {}).get("chat", {}).get("id"))
        msg_id = query.get("message", {}).get("message_id")
        
        if self.chat_id and sender_id != self.chat_id:
            return  # Unauthorized

        # Rate limiting check (3 second cooldown)
        now = time.time()
        last_click = self.callback_cooldowns.get(sender_id, 0)
        if now - last_click < 3:
            # We don't send a message here because it might spam the chat even more,
            # but we answer the callback query to clear the spinner.
            # Usually handled in poll_updates, but good for defense-in-depth here.
            return

        self.callback_cooldowns[sender_id] = now

        if data == "panic_cancel":
            if msg_id:
                self.delete_message(msg_id)
            self.send_message("✅ <b>Pánico cancelado.</b> El bot sigue operando normalmente.")
            return

        if data == "panic_confirm":
            if msg_id:
                self.delete_message(msg_id)
            self._execute_panic()
            return

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
                            continue

                        # Handle text commands and button presses
                        text_lower = text.lower().strip()
                        if text_lower.startswith("/") or text_lower in ["🛑 panic", "▶️ resume"]:
                            parts = text_lower.split()
                            # Use the full text for our custom buttons, or split parts for slash commands
                            cmd = text_lower if text_lower in ["🛑 panic", "▶️ resume"] else parts[0]
                            self.handle_command(cmd, parts[1:], sender_id=sender_id)
                            
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
