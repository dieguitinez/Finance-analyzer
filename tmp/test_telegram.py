import os
from dotenv import load_dotenv
from src.notifications import NotificationManager

def test_telegram():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"Testing Telegram with Token: {token[:10]}... and Chat ID: {chat_id}")
    
    success, message = NotificationManager.send_telegram(
        "Nivo FX - Prueba de Conexion Exitosa. Tu bot esta vinculado.",
        token,
        chat_id
    )
    
    if success:
        print("✅ Success: Message sent!")
    else:
        print(f"❌ Failed: {message}")

if __name__ == "__main__":
    test_telegram()
