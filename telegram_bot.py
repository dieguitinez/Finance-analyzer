"""
Nivo FX - Telegram Bot Command Interface
=========================================
Corre como servicio separado (nivo-bot.service) y escucha comandos del usuario.

Comandos disponibles:
  /par EUR_USD   - Cambia el par de divisas a monitorear
  /estado        - Muestra el par actual y estado del sistema
  /ayuda         - Lista todos los comandos disponibles
  /pares         - Lista los pares soportados por OANDA
"""

import os
import sys
import time
import subprocess
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NIVO BOT: [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID", ""))
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# Pares soportados por OANDA (los más comunes)
PARES_SOPORTADOS = {
    "EUR_USD": "Euro / Dólar Americano",
    "GBP_USD": "Libra Esterlina / Dólar Americano",
    "USD_JPY": "Dólar Americano / Yen Japonés",
    "USD_CAD": "Dólar Americano / Dólar Canadiense",
    "AUD_USD": "Dólar Australiano / Dólar Americano",
    "USD_CHF": "Dólar Americano / Franco Suizo",
    "NZD_USD": "Dólar Neozelandés / Dólar Americano",
    "EUR_GBP": "Euro / Libra Esterlina",
    "EUR_JPY": "Euro / Yen Japonés",
    "GBP_JPY": "Libra Esterlina / Yen Japonés",
}

def send_message(text):
    """Envía un mensaje al chat del usuario."""
    if not TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")

def get_dashboard_url():
    """Lee la URL del dashboard directamente del archivo .env."""
    try:
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith("DASHBOARD_URL="):
                        return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return ""

def get_kill_switch():
    """Lee el estado del Kill Switch del archivo .env."""
    try:
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith("EMERGENCY_KILL_SWITCH="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                        return val == "true"
    except Exception:
        pass
    return False

def set_kill_switch(state: bool):
    """Actualiza la variable EMERGENCY_KILL_SWITCH en el archivo .env."""
    state_str = "True" if state else "False"
    try:
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()

        found = False
        new_lines = []
        for line in lines:
            if line.startswith("EMERGENCY_KILL_SWITCH="):
                new_lines.append(f'EMERGENCY_KILL_SWITCH="{state_str}"\n')
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f'\nEMERGENCY_KILL_SWITCH="{state_str}"\n')

        with open(ENV_PATH, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        logger.error(f"Error actualizando kill switch en .env: {e}")
        return False

def handle_command(text):
    """Procesa un comando recibido por Telegram."""
    text = text.strip()
    cmd_parts = text.split()
    cmd = cmd_parts[0].lower()

    if cmd == "/ayuda" or cmd == "/start":
        dashboard_url = get_dashboard_url()
        db_line = f"\n\ud83d\udcca Dashboard: {dashboard_url}" if dashboard_url else ""
        send_message(
            "🤖 NIVO FX BOT (HFT Edition)\n"
            "El sistema esta monitoreando las 10 divisas principales de OANDA cada 60 segundos.\n\n"
            "Comandos:\n"
            "/estado      — Estado general del motor\n"
            "/pares       — Divisas bajo vigilancia\n"
            "/detener     — 🛑 BOTON DE PANICO (Apaga autotrading)\n"
            "/reanudar    — ▶️ Reactiva trading autonomo\n"
            "/dashboard   — Link a la web de monitoreo\n"
            "/ayuda       — Esta ayuda"
        )

    elif cmd == "/detener":
        if set_kill_switch(True):
            send_message("🛑 **KILL SWITCH ACTIVADO** 🛑\n\nEl sistema seguirá procesando datos y enviando alertas, pero **TODAS LAS ORDENES DE COMPRA/VENTA HAN SIDO BLOQUEADAS** en OANDA.")
        else:
            send_message("⚠️ Error al activar el Kill Switch. Verifica permisos de .env")

    elif cmd == "/reanudar":
        if set_kill_switch(False):
            send_message("▶️ **TRADING AUTOMÁTICO REANUDADO** ▶️\n\nEl Motor Cuántico vuelve a tener permisos para ejecutar órdenes reales en OANDA bajo su sistema de riesgo de 3 capas.")
        else:
            send_message("⚠️ Error al desactivar el Kill Switch. Verifica permisos de .env")

    elif cmd == "/dashboard":
        dashboard_url = get_dashboard_url()
        if dashboard_url:
            send_message(f"📊 Nivo FX Dashboard:\n{dashboard_url}\n\nAbre este link para ver la IA operando en tiempo real.")
        else:
            send_message("⚠️ El Dashboard URL no esta configurado en el archivo .env")

    elif cmd == "/pares":
        try:
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith("WATCHLIST="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        pares_list = [p.strip() for p in val.split(',') if p.strip()]
                        break
        except:
            pares_list = list(PARES_SOPORTADOS.keys())
            
        pares_str = ", ".join(pares_list)
        msg = f"📋 PARES BAJO VIGILANCIA (1 min):\n{pares_str}"
        send_message(msg)

    elif cmd == "/estado":
        dashboard_url = get_dashboard_url()
        db_line = f"\n📊 Dashboard: {dashboard_url}" if dashboard_url else "\n📊 Dashboard: No configurado"
        
        try:
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith("WATCHLIST="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        pares_list = [p.strip() for p in val.split(',') if p.strip()]
                        break
        except:
            pares_list = list(PARES_SOPORTADOS.keys())
            
        pares_str = ", ".join(pares_list)
        
        # Consultar Kill Switch
        kill_switch = get_kill_switch()
        trading_status = "BLOQUEADO 🛑 (Kill Switch)" if kill_switch else "AUTONOMO ACTIVO ✅"
        
        msg = (
            f"📊 ESTADO DEL SENTINEL\n"
            f"{'='*28}\n"
            f"Motor: Alta Frecuencia (1 min)\n"
            f"Divisas: {pares_str}\n"
            f"Memoria: Optimizada (1GB RAM)\n"
            f"Trading: {trading_status}\n"
            f"{db_line}"
        )
        send_message(msg)

    else:
        send_message(
            f"❓ Comando '{cmd}' no reconocido.\n"
            f"Envía /ayuda para ver los comandos disponibles."
        )

def get_updates(offset=None):
    """Obtiene los últimos mensajes del bot via long-polling."""
    try:
        params = {"timeout": 30, "allowed_updates": ["message"]}
        if offset:
            params["offset"] = offset
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        resp = requests.get(url, params=params, timeout=35)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        logger.error(f"Error obteniendo updates: {e}")
        time.sleep(5)
        return []

def run_bot():
    """Loop principal del bot."""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado. Saliendo.")
        sys.exit(1)

    logger.info("Nivo FX Bot iniciado. Esperando comandos...")
    send_message(
        "🤖 Bot Nivo FX en línea.\n"
        "Envía /ayuda para ver los comandos disponibles."
    )

    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "")

            # Solo responder al chat autorizado
            if chat != CHAT_ID:
                logger.warning(f"Mensaje de chat no autorizado: {chat}")
                continue

            if text and text.startswith("/"):
                logger.info(f"Comando recibido: {text}")
                handle_command(text)

if __name__ == "__main__":
    run_bot()
