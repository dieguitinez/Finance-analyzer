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

    def send_message(self, text):
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def handle_command(self, command, args=[]):
        command = command.lower()
        
        if command == "/start" or command == "/help":
            help_text = (
                "🤖 <b>Nivo FX - Command Center</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Comandos disponibles:\n"
                "🔹 /status - Reporte detallado de pips/PnL\n"
                "🔹 /entries - Lista rápida de posiciones abiertas\n"
                "🔹 /market - Ver volatilidad y pares calientes\n"
                "🔹 /scan - Ver pares vigilados por el Sentinel\n"
                "🔹 /balance - Ver Equidad y Margen disponible\n"
                "🔹 /dashboard - Link a la Web Dashboard\n"
                "🔹 /oanda - Link a OANDA Hub\n"
                "🛑 /kill - BOTÓN DE PÁNICO (Cierra todo y bloquea)\n"
                "🟢 /resume - Reanudar operación bloqueada\n"
                "🔹 /help - Mostrar este mensaje\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Actualizado: 2026-03-02 15:00</i>\n"
                "<i>Nivo Partners Institutional Suite</i>"
            )
            self.send_message(help_text)

        elif command == "/dashboard":
            dashboard_url = os.getenv("DASHBOARD_URL", "https://finance-analyzer-fx.streamlit.app/")
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

        elif command == "/scan":
            watchlist = os.getenv("WATCHLIST", "No definido").split(',')
            msg = "📡 <b>Sentinel Scanning:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            for pair in watchlist:
                msg += f"• {pair.strip().replace('_', '/')}\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "Estado: 🟢 Activo (1min heartbeat)"
            self.send_message(msg)

        elif command == "/kill":
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
            
        else:
            self.send_message(f"❓ Comando desconocido: {command}. Escribe /help para ayuda.")

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
                        
                        # Security Check: Only respond to the authorized chat_id
                        if user_id != self.chat_id:
                            logger.warning(f"Unauthorized access attempt from user {user_id}")
                            continue
                        
                        if text.startswith("/"):
                            parts = text.split()
                            self.handle_command(parts[0], parts[1:])
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
