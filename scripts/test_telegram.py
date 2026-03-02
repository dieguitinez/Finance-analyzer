import os
import sys
from dotenv import load_dotenv

# Ensure project root is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.notifications import NotificationManager

def test_telegram():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"--- Telegram Connection Test ---")
    print(f"Token: {token[:10]}...{token[-5:] if token else 'None'}")
    print(f"Chat ID: {chat_id}")
    
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return

    message = "🎯 Nivo FX: Test de conexión exitoso. El bot está listo para enviar notificaciones."
    success, result = NotificationManager.send_telegram(message, token, chat_id)
    
    if success:
        print(f"✅ SUCCESS: {result}")
    else:
        print(f"❌ FAILED: {result}")

if __name__ == "__main__":
    test_telegram()
