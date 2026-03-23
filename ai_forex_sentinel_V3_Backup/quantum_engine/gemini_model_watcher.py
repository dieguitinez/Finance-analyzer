import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Path to store the last known state of models
STATE_FILE = os.path.join(os.path.dirname(__file__), "known_gemini_models.json")

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing, cannot send alert.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def check_models():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("GOOGLE_API_KEY is missing.")
        return

    genai.configure(api_key=api_key)
    
    try:
        # Fetch current models
        models = list(genai.list_models())
        current_text_models = sorted([m.name.replace('models/', '') for m in models if 'generateContent' in m.supported_generation_methods])
        
        # Load known models
        known_models = []
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    known_models = json.load(f)
            except:
                pass
                
        # Compare
        new_models = set(current_text_models) - set(known_models)
        removed_models = set(known_models) - set(current_text_models)
        
        if new_models or removed_models or not known_models:
            alert_text = "🚨 *Actualización de Modelos Gemini de Google* 🚨\n\n"
            
            if new_models:
                alert_text += "✨ **NUEVOS MODELOS DETECTADOS:**\n"
                for nm in new_models:
                    alert_text += f"- `{nm}`\n"
                alert_text += "\n"
                
            if removed_models:
                alert_text += "🗑️ **MODELOS ELIMINADOS/DEPRECADOS:**\n"
                for rm in removed_models:
                    alert_text += f"- `{rm}`\n"
                alert_text += "\n"
                
            alert_text += "*(El sistema ha guardado el nuevo estado y continuará monitoreando mañana).* 👁️"
            
            print(alert_text)
            # Only send alert if we had a previous state to avoid spam on first run
            if known_models:
                send_telegram_alert(alert_text)
                
            # Save new state
            with open(STATE_FILE, "w") as f:
                json.dump(current_text_models, f, indent=4)
        else:
            print("No changes in Gemini models. All looks stable.")
            
    except Exception as e:
        print(f"Error executing watcher: {e}")

if __name__ == "__main__":
    check_models()
