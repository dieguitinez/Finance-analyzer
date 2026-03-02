import os
import re
import requests
from twilio.rest import Client
import smtplib
import ssl
from email.message import EmailMessage

class NotificationManager:
    """
    Handles secure notifications via WhatsApp, Email, and Telegram.
    Nivo Partners Watchdog Protocol v1.1.
    """
    
    @staticmethod
    def send_telegram(message, token, chat_id):
        """
        Sends a message via Telegram Bot API.
        Uses plain text (no parse_mode) for maximum reliability.
        """
        try:
            if not all([token, chat_id]):
                return False, "Incomplete Telegram credentials"
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True, "Telegram message sent successfully"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def telegram_alert(event_type, detail, token, chat_id):
        """
        Envia una alerta Telegram pre-formateada para eventos del Sentinel.
        event_type: 'trade_triggered' | 'guardian_blocked' | 'sentinel_start' | 'sentinel_quiet' | 'error'
        """
        templates = {
            'trade_triggered': ('\U0001f680', 'MOTOR CUANTICO ACTIVADO'),
            'guardian_blocked': ('\U0001f6d1', 'GUARDIAN BLOQUEO LA OPERACION'),
            'sentinel_start':   ('\U0001f441\ufe0f',  'NIVO SENTINEL INICIANDO CICLO'),
            'sentinel_quiet':   ('\U0001f634', 'MERCADO TRANQUILO - SIN OPERACION'),
            'error':            ('\u26a0\ufe0f',  'ERROR EN EL SISTEMA'),
        }
        icon, title = templates.get(event_type, ('\u2139\ufe0f', 'NIVO FX'))
        
        # Link al dashboard
        dashboard_url = NotificationManager._get_dashboard_url()
        dashboard_line = f"\n\ud83d\udcca Dashboard: {dashboard_url}" if dashboard_url else ""
        
        msg = f"{icon} {title}\n{'='*30}\n{detail}{dashboard_line}"
        return NotificationManager.send_telegram(msg, token, chat_id)

    @staticmethod
    def _get_dashboard_url():
        """Lee la URL del dashboard directamente de .env para evitar cache de ambiente."""
        try:
            # Asumimos que .env está en el root del proyecto (un nivel arriba de /src)
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if line.startswith("DASHBOARD_URL="):
                            return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return os.getenv("DASHBOARD_URL", "")

    @staticmethod
    def trade_signal_alert(pair, signal, score, weight, direction, guardian_msg, token, chat_id):
        """
        Envia una alerta rica con la decision completa de trading.
        signal: 'BUY' | 'SELL' | 'WAIT'
        direction: Porcentaje alcista (0.0 a 1.0)
        """
        if 'BUY' in signal or 'BUY' in str(signal).upper():
            icon = '\U0001f7e2'  # verde
            dir_text = 'COMPRA (AL ALZA)'
        elif 'SELL' in signal or 'SELL' in str(signal).upper():
            icon = '\U0001f534'  # rojo
            dir_text = 'VENTA (A LA BAJA)'
        else:
            icon = '\U0001f7e1'  # amarillo
            dir_text = 'ESPERAR (SIN POSICION)'

        dir_pct = direction * 100 if isinstance(direction, float) and direction <= 1.0 else direction
        score_bar = '\u2588' * int(score / 10) + '\u2591' * (10 - int(score / 10))

        # Link al dashboard (lectura directa de archivo para evitar URLs muertas)
        dashboard_url = NotificationManager._get_dashboard_url()
        dashboard_line = f"\n\ud83d\udcca Dashboard: {dashboard_url}" if dashboard_url else ""
        oanda_line = "\n📲 OANDA: https://trade.oanda.com/"

        msg = (
            f"{icon} SENAL NIVO FX - {pair}\n"
            f"{'='*30}\n"
            f"Direccion:   {dir_text}\n"
            f"Score:       {score:.1f}/100\n"
            f"             [{score_bar}]\n"
            f"Peso:        {weight:.2f}x apalancamiento\n"
            f"Prob. Alcista: {dir_pct:.1f}%\n"
            f"Guardian:    {guardian_msg}\n"
            f"{'='*30}\n"
            f"Senyal Final: {signal}"
            f"{dashboard_line}"
            f"{oanda_line}"
        )
        return NotificationManager.send_telegram(msg, token, chat_id)

    @staticmethod
    def trade_execution_report(pair, action, units, order_id, token, chat_id):
        """
        Confirma la ejecucion real en el broker con el ID de transaccion.
        """
        icon = '\u2705' # check mark
        oanda_link = "https://trade.oanda.com/"
        
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        msg = (
            f"{icon} EJECUCION CONFIRMADA\n"
            f"{'='*30}\n"
            f"Hora:        {now}\n"
            f"Instrumento: {pair}\n"
            f"Operacion:   {'COMPRA' if int(units) > 0 else 'VENTA'}\n"
            f"Unidades:    {abs(int(units))}\n"
            f"Transaccion: {order_id}\n"
            f"{'='*30}\n"
            f"\ud83d\udcf1 Ver en OANDA: {oanda_link}"
        )
        return NotificationManager.send_telegram(msg, token, chat_id)

    @staticmethod
    def send_whatsapp(message, sid, token, from_num, to_num):
        try:
            if not all([sid, token, from_num, to_num]):
                return False, "Incomplete Twilio credentials"
            client = Client(sid, token)
            msg = client.messages.create(
                body=message, 
                from_=f"whatsapp:{from_num.replace('whatsapp:', '')}", 
                to=f"whatsapp:{to_num.replace('whatsapp:', '')}"
            )
            return True, msg.sid
        except Exception as e:
            return False, str(e)

    @staticmethod
    def send_email(subject, body, sender, password, receiver):
        try:
            if not all([sender, password, receiver]):
                return False, "Incomplete Email credentials"
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = receiver
            
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(sender, password)
                server.send_message(msg)
            return True, "Email sent successfully"
        except Exception as e:
            return False, str(e)
