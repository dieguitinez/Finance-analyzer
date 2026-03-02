import os
from dotenv import load_dotenv

# Ensure we use Nivo FX notification manager
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.notifications import NotificationManager

def test_broadcast():
    load_dotenv()
    
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID")
    
    if not tg_token or not tg_chat:
        print("Missing primary Telegram credentials.")
        return
        
    print(f"Testing primary chat: {tg_chat}")
    
    # We temporarily set a dummy broadcast ID just to see if the logic triggers
    # without crashing. In real life, the user provides a real ID.
    real_broadcast = os.getenv("TELEGRAM_BROADCAST_CHAT_ID")
    
    if not real_broadcast:
        print("No TELEGRAM_BROADCAST_CHAT_ID found in .env, simulating one...")
        os.environ["TELEGRAM_BROADCAST_CHAT_ID"] = tg_chat # Send to main chat for test
        
    print("Sending broadcast test message...")
    
    try:
        NotificationManager.broadcast_message(
            "Mensaje de Prueba para el Canal de Broadcast (Solo Lectura) del Inversor.",
            "info",
            os.getenv("TELEGRAM_BOT_TOKEN"),
            os.getenv("TELEGRAM_CHAT_ID")
        )
        print("✅ Broadcast test completed successfully!")
    except Exception as e:
        print(f"❌ Broadcast test failed: {e}")
        
    # Restore original environment
    if not real_broadcast and "TELEGRAM_BROADCAST_CHAT_ID" in os.environ:
        del os.environ["TELEGRAM_BROADCAST_CHAT_ID"]

if __name__ == '__main__':
    test_broadcast()
