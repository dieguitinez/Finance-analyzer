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
                "text": message,
                "parse_mode": "HTML"
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
            icon = '🟢'  # verde
            dir_text = '📈 COMPRA / LONG (AL ALZA)'
        elif 'SELL' in signal or 'SELL' in str(signal).upper():
            icon = '🔴'  # rojo
            dir_text = '📉 VENTA / SHORT (A LA BAJA)'
        else:
            icon = '🟡'  # amarillo
            dir_text = '⏳ ESPERAR (SIN POSICIÓN)'

        dir_pct = direction * 100 if isinstance(direction, float) and direction <= 1.0 else direction
        score_bar = '\u2588' * int(score / 10) + '\u2591' * (10 - int(score / 10))

        # Link al dashboard (lectura directa de archivo para evitar URLs muertas)
        dashboard_url = NotificationManager._get_dashboard_url()
        dashboard_line = f"\n\ud83d\udcca Dashboard: {dashboard_url}" if dashboard_url else ""
        oanda_line = "\n📲 OANDA: https://trade.oanda.com/"

        msg = (
            f"{icon} <b>NIVO QUANTUM SIGNAL - {pair}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Decisión:</b> {dir_text}\n"
            f"🔥 <b>Intensidad:</b> {score_bar} ({score:.1f}%)\n"
            f"🎯 <b>Confianza AI:</b> {dir_pct:.1f}%\n"
            f"⚖️ <b>Apancalamiento:</b> {weight:.2f}x\n"
            f"🛡️ <b>Guardian:</b> {guardian_msg}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
            f"{dashboard_line}"
            f"{oanda_line}"
        )
        return NotificationManager.send_telegram(msg, token, chat_id)

    @staticmethod
    def broadcast_message(message, level, token, chat_id):
        """
        Envía un mensaje a un chat principal y opcionalmente a un canal de broadcast.
        Permite categorizar el mensaje con un 'level' para un encabezado predefinido.
        
        Args:
            message (str): El cuerpo del mensaje a enviar.
            level (str): Categoría del mensaje ('info', 'warning', 'error', 'trade').
            token (str): Token del bot de Telegram.
            chat_id (str): ID del chat principal (administrador).
            
        Pasos:
        1. Determinar el encabezado basado en el nivel.
        2. Formatear el mensaje completo.
        3. Generar mensaje consolidado
        4. Opcional: Enviar también a un canal de solo lectura (Broadcast Channel)
        """
        import os
        header = {
            'info': "ℹ️ <b>INFO</b>",
            'warning': "⚠️ <b>ADVERTENCIA</b>",
            'error': "🚨 <b>ERROR CRÍTICO</b>",
            'trade': "📊 <b>TRADE EJECUTADO</b>"
        }.get(level, "🔔 <b>NOTIFICACIÓN</b>")
        
        full_message = f"{header}\n───────────────────\n{message}"
        
        # Enviar al chat principal del administrador
        NotificationManager.send_telegram(full_message, token, chat_id)
        
        # Enviar copia al canal de broadcast (solo lectura) si existe
        broadcast_chat_id = os.getenv("TELEGRAM_BROADCAST_CHAT_ID")
        if broadcast_chat_id and str(broadcast_chat_id).strip() != "":
            # Añadir un tag para que el canal sepa que es un broadcast auditado
            broadcast_msg = f"{full_message}\n\n<i>(Nivo FX Automated Broadcast)</i>"
            NotificationManager.send_telegram(broadcast_msg, token, broadcast_chat_id)

    @staticmethod
    def position_performance_report(pair, units, entry_price, current_price, exit_price, sl_price, insured_pips, pips, pnl_usd, token, chat_id):
        """
        Informa sobre el rendimiento de una posicion abierta en tiempo real.
        """
        icon = '\ud83d\udcc8' if pips >= 0 else '\ud83d\udcc9'
        trend_icon = '\U0001f4c8' if pips >= 0 else '\U0001f4c9'
        
        oanda_link = "https://trade.oanda.com/"
        
        exit_line = f"🚪 <b>Estim. Salida:</b> {exit_price:.5f} (TS)\n" if exit_price > 0 else ""
        sl_line = f"🛡️ <b>Stop Loss:</b> {sl_price:.5f}\n" if sl_price > 0 else ""
        
        # Highlight if protected (Break-even or better)
        is_protected = False
        if units > 0 and sl_price >= entry_price: is_protected = True
        if units < 0 and sl_price > 0 and sl_price <= entry_price: is_protected = True
        
        guard_msg = f" ✅ <b>SECURED: +{insured_pips:.1f} PIPS</b>" if insured_pips > 0 else " 🛡️ <b>BREAK-EVEN</b>" if is_protected else ""
        
        msg = (
            f"{icon} <b>SEGUIMIENTO - {pair}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Estado:</b> ABIERTA {trend_icon}{guard_msg}\n"
            f"🏗️ <b>Operación:</b> {'📈 COMPRA / LONG' if float(units) > 0 else '📉 VENTA / SHORT'}\n"
            f"🏁 <b>Entrada:</b> {entry_price:.5f}\n"
            f"💹 <b>Precio Actual:</b> {current_price:.5f}\n"
            f"{sl_line}"
            f"{exit_line}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Pips:</b> {pips:+.1f} pips\n"
            f"💵 <b>Beneficio:</b> ${pnl_usd:+.2f} USD\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📲 <a href='{oanda_link}'>Gestionar en OANDA</a>"
        )
        return NotificationManager.send_telegram(msg, token, chat_id)

    @staticmethod
    def trade_execution_report(pair, action, units, order_id, token, chat_id):
        """
        Confirma la ejecucion real en el broker con el ID de transaccion.
        Incluye boton de panico inline para cierre de emergencia.
        """
        oanda_link = "https://trade.oanda.com/"

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        direction_icon = '📈' if int(units) > 0 else '📉'
        direction_text = 'COMPRA (LONG)' if int(units) > 0 else 'VENTA (SHORT)'

        msg = (
            f"✅ <b>EJECUCION CONFIRMADA</b>\n"
            f"{'─'*24}\n"
            f"🕐 <b>Hora:</b>         {now}\n"
            f"📊 <b>Par:</b>          {pair}\n"
            f"{direction_icon} <b>Operacion:</b>   {direction_text}\n"
            f"📦 <b>Unidades:</b>     {abs(int(units)):,}\n"
            f"🔖 <b>Transaccion:</b>  {order_id}\n"
            f"{'─'*24}\n"
            f"📱 <a href='{oanda_link}'>Ver en OANDA</a>"
        )

        # Inline keyboard with panic kill switch button
        reply_markup = {
            "inline_keyboard": [[
                {"text": "🛑 KILL SWITCH — Cerrar Todo", "callback_data": "/kill"}
            ]]
        }

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": reply_markup
            }, timeout=10)
        except Exception:
            # Fallback: plain message without button
            try:
                requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
            except Exception:
                pass

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
