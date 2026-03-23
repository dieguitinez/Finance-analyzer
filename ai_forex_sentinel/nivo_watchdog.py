import os
import time
import shutil
import logging
import psutil
import requests
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | WATCHDOG: [%(levelname)s] | %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Config
RAM_THRESHOLD_PCT = 90
MAX_LOG_SIZE_MB = 100
CHECK_INTERVAL_SEC = 300 # 5 minutes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LOG_FILES = [
    os.path.join(os.path.dirname(__file__), "quantum_engine", "sentinel.log"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai_stock_sentinel", "sentinel.log"),
    "stock-watcher.service_output.log"
]

def send_critical_alert(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 <b>NIVO WATCHDOG ALERT</b>\n━━━━━━━━━━━━\n{message}",
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send watchdog alert: {e}")

def rotate_logs():
    for log_path in LOG_FILES:
        if os.path.exists(log_path):
            size_mb = os.path.getsize(log_path) / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                logger.info(f"Rotating log {log_path} (Size: {size_mb:.2f} MB)")
                backup_path = f"{log_path}.old"
                try:
                    shutil.move(log_path, backup_path)
                    # Create empty new log
                    with open(log_path, 'w') as f:
                        f.write(f"--- Log rotated by Nivo Watchdog at {time.ctime()} ---\n")
                    logger.info(f"Successfully rotated {log_path}")
                except Exception as e:
                    logger.error(f"Error rotating {log_path}: {e}")

def monitor_memory():
    mem = psutil.virtual_memory()
    if mem.percent > RAM_THRESHOLD_PCT:
        msg = (
            f"⚠️ <b>RAM CRITICA: {mem.percent}%</b>\n"
            f"Uso: {mem.used / (1024**3):.2f}GB / {mem.total / (1024**3):.2f}GB\n"
            f"Acción: El sistema podría congelarse. Reinicie servicios o libere memoria inmediatamente."
        )
        logger.warning(msg)
        send_critical_alert(msg)
    else:
        logger.info(f"Memory Check: {mem.percent}% (OK)")

def run_watchdog():
    logger.info("Nivo Partners Watchdog started.")
    while True:
        try:
            rotate_logs()
            monitor_memory()
        except Exception as e:
            logger.error(f"Error in watchdog loop: {e}")
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    run_watchdog()
