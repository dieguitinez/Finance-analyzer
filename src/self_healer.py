import os
import json
import logging
import traceback
from google import genai
from src.notifications import NotificationManager

logger = logging.getLogger(__name__)

class NivoSelfHealer:
    """
    Self-Healing and AI Diagnostic Layer for Nivo FX.
    """
    
    @staticmethod
    def get_ticker_fallbacks(pair):
        """
        Generates alternative ticker names for Yahoo Finance.
        Example: USD/JPY -> [JPY=X, USDJPY=X]
        """
        parts = pair.replace("/", "_").split("_")
        if len(parts) != 2:
            return []
            
        base, quote = parts[0], parts[1]
        
        # Fallbacks ordered by likelihood for Yahoo Finance
        fallbacks = [
            f"{base}{quote}=X",
            f"{quote}{base}=X",
            f"{base}=X",
            f"{quote}=X"
        ]
        return list(dict.fromkeys(fallbacks))

    @staticmethod
    def diagnose_with_ai(error_msg, context=""):
        """
        Uses Gemini API to explain the error and suggest a fix.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "⚠️ Gemini API no configurada para diagnósticos."
            
        try:
            # The new SDK automatically picks up GOOGLE_API_KEY from environment, 
            # but we'll be explicit for clarity.
            client = genai.Client(api_key=api_key)
            
            prompt = f"""
            Eres el Nivo FX Self-Healer. 
            Nuestro bot de trading algorítmico ha fallado silenciosamente o ha lanzado una excepción.
            Error: {error_msg}
            Contexto técnico: {context}
            
            Como ingeniero experto, explica brevemente en español qué pasó y cómo arreglarlo o mitigarlo. 
            Sé directo. Máximo 3 o 4 líneas.
            """
            
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            return f"⚠️ Error consultando a la IA para diagnóstico: {str(e)}"

    @staticmethod
    def diagnose_and_alert(component, error_msg, exception_obj=None, context_data=None):
        """
        Sends a deep diagnostic alert to Telegram with the AI's assessment and a copy-paste payload.
        """
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat = os.getenv("TELEGRAM_CHAT_ID")
        
        if not tg_token or not tg_chat:
            logger.error("No Telegram credentials for Self-Healer alert.")
            return

        # Prepare traceback if available
        trace = ""
        if exception_obj:
            try:
                trace_list = traceback.format_exception(type(exception_obj), exception_obj, exception_obj.__traceback__)
                trace = "".join(trace_list)
            except:
                trace = str(exception_obj)

        trace_snippet = trace[-500:] if len(trace) > 500 else trace
        full_context = f"Data: {context_data}\nTrace snippet: {trace_snippet}"
        
        # 1. Get AI Explanation
        ai_hint = NivoSelfHealer.diagnose_with_ai(error_msg, full_context)
        
        # 2. Create Payload for the Assistant
        diagnostic_payload = {
            "component": component,
            "error": str(error_msg),
            "context": context_data,
            "trace_snippet": trace_snippet if trace_snippet else None
        }
        
        payload_str = json.dumps(diagnostic_payload, indent=2)
        
        # 3. Format and Send Telegram Message
        msg = (
            f"🆘 **AUTO-FIX TRIGGERED: {component}**\n"
            f"───────────────────\n"
            f"❌ **Error Detectado:**\n{error_msg}\n\n"
            f"🧠 **Diagnóstico IA:**\n{ai_hint}\n\n"
            f"🛠 **Diagnostic Payload (Copia esto al chat de Antigravity):**\n"
            f"```json\n{payload_str}\n```"
        )
        
        NotificationManager.send_telegram(msg, tg_token, tg_chat)
