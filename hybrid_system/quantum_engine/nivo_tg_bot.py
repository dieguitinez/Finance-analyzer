import os
import time
import requests
import json
import logging
from dotenv import load_dotenv

# Ensure project root is importable
import sys
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.auto_execution import NivoAutoTrader
from src.notifications import NotificationManager

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NIVO BOT: [%(levelname)s] | %(message)s'
)
logger = logging.getLogger(__name__)

class NivoTelegramBot:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        
        # OANDA Setup
        self.api_key = os.getenv("OANDA_ACCESS_TOKEN")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID")
        self.env = "practice" if "practice" in os.getenv("OANDA_BASE_URL", "practice") else "live"
        self.trader = NivoAutoTrader(self.api_key, self.account_id, environment=self.env) if self.api_key else None

    def send_message(self, text, reply_markup=None):
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            requests.post(url, json=payload)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def delete_message(self, message_id):
        url = f"{self.api_url}/deleteMessage"
        payload = {"chat_id": self.chat_id, "message_id": message_id}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")

    def handle_command(self, command, args=[]):
        command = command.lower()
        
        if command in ["/start", "/help", "/ayuda"]:
            help_text = (
                "🤖 <b>Nivo FX - Command Center</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Comandos disponibles:\n"
                "🔹 /status - Reporte detallado de pips/PnL\n"
                "🔹 /entries - Lista rápida de posiciones abiertas\n"
                "🔹 /report EUR_USD - Diagnóstico interno completo (cerebro del Bot)\n"
                "🔹 /close  - Cerrar una posición específica\n"
                "🔹 /market - Ver volatilidad y pares calientes\n"
                "🔹 /balance - Ver Equidad y Margen disponible\n"
                "🔹 /dashboard - Link a la Web Dashboard\n"
                "🔹 /oanda - Link a OANDA Hub\n"
                "🛑 /kill (🛑 PANIC) - BOTÓN DE PÁNICO (Cierra todo y bloquea)\n"
                "🟢 /resume (▶️ RESUME) - Reanudar operación bloqueada\n"
                "🔹 /help - Mostrar este mensaje\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Actualizado: 2026-03-05</i>\n"
                "<i>Nivo Partners Institutional Suite</i>"
            )
            keyboard_markup = {
                "keyboard": [
                    [{"text": "/status"}, {"text": "/entries"}, {"text": "/balance"}],
                    [{"text": "/market"}, {"text": "/close"}, {"text": "/ayuda"}],
                    [{"text": "🛑 PANIC"}, {"text": "▶️ RESUME"}]
                ],
                "resize_keyboard": True,
                "is_persistent": True
            }
            self.send_message(help_text, reply_markup=keyboard_markup)

        elif command == "/dashboard":
            dashboard_url = os.getenv("DASHBOARD_URL", "https://finance-analyzer-fx.streamlit.app")
            self.send_message(f"🌐 <b>Dashboard En Vivo:</b>\n{dashboard_url}")

        elif command == "/oanda":
            self.send_message("🏦 <b>OANDA Hub:</b>\nhttps://hub.oanda.com/")

        elif command == "/status":
            if not self.trader:
                self.send_message("❌ Error: OANDA API no configurada.")
                return
            
            self.send_message("🔍 Consultando portafolio detallado...")
            
            try:
                # Optimized: Get only active instruments first instead of looping through entire watchlist
                pos_response = self.trader.ctx.position.list_open(self.account_id)
                positions = pos_response.get("positions", 200)
                
                if not positions:
                    self.send_message("✅ <b>Portafolio Limpio.</b> No hay posiciones abiertas.")
                    return

                for pos in positions:
                    symbol = pos.instrument
                    perf = self.trader.get_position_performance(symbol)
                    if perf:
                        NotificationManager.position_performance_report(
                            pair=symbol.replace("_", "/"),
                            units=perf['units'],
                            entry_price=perf['entry_price'],
                            current_price=perf['current_price'],
                            sl_price=perf.get('sl_price', 0),
                            exit_price=perf.get('exit_price', 0),
                            insured_pips=perf.get('insured_pips', 0),
                            pips=perf['pips'],
                            pnl_usd=perf['pnl_usd'],
                            token=self.token,
                            chat_id=self.chat_id
                        )
            except Exception as e:
                self.send_message(f"❌ Error al consultar estatus: {e}")

        elif command == "/entries":
            if not self.trader:
                self.send_message("❌ Error: API no configurada.")
                return
            
            try:
                response = self.trader.ctx.position.list_open(self.account_id)
                positions = response.get("positions", 200)
                if not positions:
                    self.send_message("✅ No hay entradas abiertas actualmente.")
                    return
                
                msg = "📝 <b>Entradas Abiertas:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for pos in positions:
                    symbol = pos.instrument
                    long_units = float(pos.long.units)
                    short_units = float(pos.short.units)
                    units = long_units if long_units != 0 else short_units
                    side = "🟢 LONG" if units > 0 else "🔴 SHORT"
                    pnl = float(pos.unrealizedPL)
                    msg += f"{side} <b>{symbol}</b>: {int(abs(units))} ud | PnL: ${pnl:.2f}\n"
                msg += "━━━━━━━━━━━━━━━━━━━━"
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al listar entradas: {e}")

        elif command == "/balance":
            if not self.trader:
                self.send_message("❌ Error: API no configurada.")
                return
            try:
                response = self.trader.ctx.account.summary(self.account_id)
                acc = response.get("account", 200)
                msg = (
                    "💰 <b>Estado de Cuenta:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 <b>Balance:</b> ${float(acc.balance):,.2f}\n"
                    f"📈 <b>Equidad (NAV):</b> ${float(acc.NAV):,.2f}\n"
                    f"💎 <b>Margen Disp:</b> ${float(acc.marginAvailable):,.2f}\n"
                    f"📊 <b>PnL Abierto:</b> ${float(acc.unrealizedPL):,.2f}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
                self.send_message(msg)
            except Exception as e:
                self.send_message(f"❌ Error al consultar balance: {e}")

        elif command == "/market":
            # For now, a placeholder that lists the watchlist
            watchlist = os.getenv("WATCHLIST", "No definido")
            msg = (
                "📊 <b>Market Watchlist</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"Pares monitoreados:\n<code>{watchlist}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "El Sentinel está escaneando volatilidad cada minuto."
            )
            self.send_message(msg)

        elif command in ["/kill", "/panic", "� panic"]:
            self.send_message("🚨 <b>PROTOCOL: EMERGENCY KILL SWITCH</b>\nIniciando secuencia de detención total...")
            try:
                # 1. Create Persistent Lock File
                lock_file = os.path.join(_project_root, ".panic_lock")
                with open(lock_file, "w") as f:
                    f.write(f"Killed by Telegram at {time.ctime()}")
                
                # 2. Force Close All Positions
                if self.trader:
                    res = self.trader.close_all_positions()
                    if res.get("status") == "success":
                        self.send_message("✅ <b>SISTEMA DETENIDO.</b> Todas las posiciones han sido cerradas y el motor de ejecución está bloqueado.")
                    else:
                        self.send_message(f"⚠️ Motor bloqueado, pero hubo un error al cerrar posiciones: {res.get('message')}")
                else:
                    self.send_message("✅ <b>MOTOR BLOQUEADO.</b> (No se detectó configuración de OANDA para cerrar posiciones).")
            except Exception as e:
                self.send_message(f"❌ Error crítico en Protocolo Kill: {e}")

        elif command == "/resume":
            lock_file = os.path.join(_project_root, ".panic_lock")
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                    self.send_message("🟢 <b>SISTEMA REANUDADO.</b> El motor de ejecución ha sido desbloqueado y volverá a operar en el próximo ciclo.")
                except Exception as e:
                    self.send_message(f"❌ Error al intentar reanudar: {e}")
            else:
                self.send_message("ℹ️ El sistema ya se encuentra en estado operativo (No había bloqueo activo).")
            
        elif command == "/report":
            requested_raw = args[0].upper().replace("/", "_") if args else ""
            if not requested_raw:
                _all_pairs = [
                    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD",
                    "USD_CAD", "USD_CHF", "NZD_USD", "EUR_GBP",
                    "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY",
                    "EUR_AUD", "EUR_CHF", "CHF_JPY"
                ]
                buttons, row = [], []
                for i, p in enumerate(_all_pairs):
                    row.append({"text": p.replace("_", "/"), "callback_data": f"report:{p}"})
                    if len(row) == 3:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                try:
                    requests.post(f"{self.api_url}/sendMessage", json={
                        "chat_id": self.chat_id,
                        "text": "🔬 <b>¿Qué par deseas diagnosticar?</b>\nToca un par para ver el análisis interno completo:",
                        "parse_mode": "HTML",
                        "reply_markup": {"inline_keyboard": buttons}
                    }, timeout=10)
                except Exception as e:
                    self.send_message(f"❌ Error: {e}")
                return

            self.send_message(f"🔬 Diagnóstico para <b>{requested_raw.replace('_','/')}</b>... ⏳ ~15s")

            try:
                import subprocess
                import json
                import copy

                env = copy.copy(os.environ)
                env["TRADING_PAIR"] = requested_raw

                vm_path = os.path.join(_project_root, "quantum_engine", "vm_executor.py")
                result = subprocess.run(
                    ["python3", vm_path, "--diagnostic"],
                    capture_output=True, text=True, timeout=35, env=env,
                    cwd=_project_root
                )

                json_line = None
                for line in reversed(result.stdout.strip().split("\n")):
                    if line.strip().startswith("{"):
                        json_line = line.strip()
                        break

                if not json_line:
                    self.send_message(f"❌ Sin reporte JSON.\n<code>{result.stderr[-300:]}</code>")
                    return

                d = json.loads(json_line)
                if "error" in d:
                    self.send_message(f"❌ Error en diagnóstico: {d['error']}")
                    return

                pair_display = d.get("pair", requested_raw.replace("_", "/"))
                price = d.get("current_price", "N/A")
                ts = str(d.get("timestamp", ""))[:16]
                lh = d.get("left_hemisphere", {})
                rh = d.get("right_hemisphere", {})
                fd = d.get("fundamental", {})
                qb = d.get("quantum_bridge", {})
                decision = d.get("decision", "UNKNOWN")

                dec_icon = "📈" if decision == "BUY" else "📉" if decision == "SELL" else "⏸" if decision == "WAIT" else "🛑"
                lstm_badge = "✅ Entrenado" if rh.get("lstm_trained") else "⚠️ Aleatorio"
                lstm_prob = float(rh.get('lstm_bull_prob', 50))
                lstm_bar  = "🟢" if lstm_prob > 60 else "🔴" if lstm_prob < 40 else "🟡"
                tech      = float(lh.get('tech_score', 50))
                tech_bar  = "🟢" if tech > 60 else "🔴" if tech < 40 else "🟡"
                fscore    = float(qb.get('final_score', 50))
                fs_bar    = "🟢" if fscore > 60 else "🔴" if fscore < 40 else "🟡"
                veto_line = f"\n  🛑 <b>VETO:</b> {rh.get('veto_reason')}" if rh.get("cortex_veto") else ""

                msg = (
                    f"🔬 <b>DIAGNÓSTICO — {pair_display}</b>\n"
                    f"🕐 {ts}  |  💲 {price}\n"
                    f"{'═'*22}\n"
                    f"\n🧠 <b>HEMISFERIO IZQUIERDO (Técnico)</b>\n"
                    f"  Score: {tech_bar} <b>{lh.get('tech_score')}/100</b>  |  Señal: {lh.get('signal','N/A')}\n"
                    f"  RSI: {lh.get('rsi','N/A')}  |  MACD: {lh.get('macd_signal','N/A')}\n"
                    f"\n🤖 <b>HEMISFERIO DERECHO (IA)</b>\n"
                    f"  HMM Régimen: <b>{rh.get('hmm_regime','N/A')}</b>\n"
                    f"  LSTM Bull:   {lstm_bar} <b>{lstm_prob}%</b>  [{lstm_badge}]{veto_line}\n"
                    f"\n📰 <b>FUNDAMENTAL</b>\n"
                    f"  Sentiment: <b>{fd.get('sentiment_score','N/A')}/100</b>  |  Headlines: {fd.get('headline_count','N/A')}\n"
                    f"\n⚛️ <b>PUENTE CUÁNTICO</b>\n"
                    f"  Score Final: {fs_bar} <b>{fscore}/100</b>  |  Q-Mult: {qb.get('q_multiplier','N/A')}x\n"
                    f"{'═'*22}\n"
                    f"{dec_icon} <b>DECISIÓN: {decision}</b>\n"
                    f"<i>BUY &gt;60 | SELL &lt;40 | WAIT en el medio</i>"
                )
                self.send_message(msg)

            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Timeout: diagnóstico tardó más de 35s.")
            except Exception as e:
                self.send_message(f"❌ Error: {e}")

        elif command == "/close":
            if not self.trader:
                self.send_message("❌ Error: OANDA API no configurada.")
                return
            try:
                response = self.trader.ctx.position.list_open(self.account_id)
                positions = response.get("positions", 200)
                if not positions:
                    self.send_message("✅ No hay posiciones abiertas para cerrar.")
                    return

                # Build one button per open position
                buttons = []
                for pos in positions:
                    symbol = pos.instrument  # e.g. 'EUR_USD'
                    long_units = float(pos.long.units)
                    short_units = float(pos.short.units)
                    pnl = float(pos.unrealizedPL)
                    side = "📈 L" if long_units > 0 else "📉 S"
                    pnl_str = f"${pnl:+.2f}"
                    label = f"{side} {symbol.replace('_','/')}  {pnl_str}"
                    buttons.append([{"text": label, "callback_data": f"close:{symbol}"}])

                # Add a cancel button at the bottom
                buttons.append([{"text": "🚫 Cancelar", "callback_data": "close:CANCEL"}])

                reply_markup = {"inline_keyboard": buttons}
                url = f"{self.api_url}/sendMessage"
                try:
                    requests.post(url, json={
                        "chat_id": self.chat_id,
                        "text": "📋 <b>¿Qué posición deseas cerrar?</b>\nToca el par para cerrarlo inmediatamente:",
                        "parse_mode": "HTML",
                        "reply_markup": reply_markup
                    }, timeout=10)
                except Exception as e:
                    self.send_message(f"❌ Error mostrando menú: {e}")
            except Exception as e:
                self.send_message(f"❌ Error al obtener posiciones: {e}")

        else:
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /help para ayuda.")

    def _execute_panic(self):
        self.send_message("🚨 <b>PROTOCOL: EMERGENCY KILL SWITCH</b>\nIniciando secuencia de detención total...")
        try:
            # 1. Create Persistent Lock File
            lock_file = os.path.join(_project_root, ".panic_lock")
            with open(lock_file, "w") as f:
                f.write(f"Killed by Telegram at {time.ctime()}")
            
            # 2. Force Close All Positions
            if getattr(self, "trader", None):
                res = self.trader.close_all_positions()
                if res.get("status") == "success":
                    self.send_message("✅ <b>SISTEMA DETENIDO.</b> Todas las posiciones han sido cerradas y el motor de ejecución está bloqueado.")
                else:
                    self.send_message(f"⚠️ Motor bloqueado, pero hubo un error al cerrar posiciones: {res.get('message')}")
            else:
                self.send_message("✅ <b>MOTOR BLOQUEADO.</b> (No se detectó configuración de OANDA para cerrar posiciones).")
        except Exception as e:
            self.send_message(f"❌ Error crítico en Protocolo Kill: {e}")

    def poll_updates(self):
        url = f"{self.api_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]

                    # Handle inline keyboard button taps (callback_query)
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        cq_id = cq["id"]
                        user_id = str(cq["message"]["chat"]["id"])
                        callback_data = cq.get("data", "")

                        # Answer the callback to dismiss the loading spinner
                        try:
                            requests.post(
                                f"{self.api_url}/answerCallbackQuery",
                                json={"callback_query_id": cq_id, "text": "⚡ Ejecutando..."},
                                timeout=5
                            )
                        except Exception:
                            pass

                        # Security: only authorized chat
                        if user_id == self.chat_id:
                            if callback_data == "panic_cancel":
                                if "message" in cq and "message_id" in cq["message"]:
                                    self.delete_message(cq["message"]["message_id"])
                                self.send_message("✅ <b>Pánico cancelado.</b> El Sentinel sigue operando normalmente.")
                            elif callback_data == "panic_confirm":
                                if "message" in cq and "message_id" in cq["message"]:
                                    self.delete_message(cq["message"]["message_id"])
                                self._execute_panic()
                            elif callback_data.startswith("/"):
                                # Command button (e.g. /kill)
                                parts = callback_data.split()
                                self.handle_command(parts[0], parts[1:])
                            elif callback_data.startswith("report:"):
                                # Pair report picker button
                                instrument = callback_data.split(":", 1)[1]
                                self.handle_command("/report", [instrument])
                            elif callback_data.startswith("close:"):
                                # Close single position button
                                instrument = callback_data.split(":", 1)[1]
                                if instrument == "CANCEL":
                                    self.send_message("🚫 Operación cancelada. No se cerró ninguna posición.")
                                elif self.trader:
                                    self.send_message(f"⏳ Cerrando posición en <b>{instrument.replace('_','/')}</b>...", )
                                    result = self.trader.close_single_position(instrument)
                                    if result.get("status") == "success":
                                        pl = result.get("pl", 0)
                                        pl_icon = "✅" if pl >= 0 else "🔴"
                                        self.send_message(
                                            f"{pl_icon} <b>Posición Cerrada</b>\n"
                                            f"{'─'*20}\n"
                                            f"📊 Par: <b>{instrument.replace('_','/')}</b>\n"
                                            f"💰 PnL Realizado: <b>${pl:+.2f}</b>\n"
                                            f"{'─'*20}"
                                        )
                                    else:
                                        self.send_message(f"❌ Error al cerrar {instrument}: {result.get('message')}")
                        continue

                    # Handle regular text commands
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"]
                        user_id = str(update["message"]["chat"]["id"])
                        
                        # Security Check: Only respond to the authorized chat_id
                        if user_id != self.chat_id:
                            logger.warning(f"Unauthorized access attempt from user {user_id}")
                            continue
                        
                        text_lower = text.lower().strip()
                        if text_lower.startswith("/") or text_lower in ["🛑 panic", "▶️ resume"]:
                            parts = text_lower.split()
                            cmd = text_lower if text_lower in ["🛑 panic", "▶️ resume"] else parts[0]
                            self.handle_command(cmd, parts[1:])
            else:
                logger.error(f"Polling error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error polling: {e}")

    def run(self):
        logger.info("Nivo Telegram Bot started. Listening for commands...")
        while True:
            self.poll_updates()
            time.sleep(1)

if __name__ == "__main__":
    bot = NivoTelegramBot()
    bot.run()
