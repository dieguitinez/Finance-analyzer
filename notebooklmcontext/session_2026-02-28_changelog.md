# Session Changelog — 2026-02-28

## ✅ Lo que se completó en esta sesión

### 1. Deploy a Linux Mint (HP ENVY x360 Convertible)
- **Usuario Linux:** `diego`
- **IP del servidor:** `192.168.1.240`
- **Conexión:** VS Code Remote SSH ya configurado desde sesiones anteriores
- **Script creado:** `deploy_to_linux.ps1` (en la raíz del proyecto, en Windows)

### 2. Cómo correr el deploy script en el futuro
Desde **PowerShell en Windows** (NO desde el terminal SSH):
```powershell
cd "c:\Users\qqqq\.gemini\antigravity\playground\Finance Analyzer"
.\deploy_to_linux.ps1 -RemoteUser "diego" -RemoteIP "192.168.1.240"
```
- La `ExecutionPolicy` ya fue configurada (`RemoteSigned -Scope CurrentUser`), no hay que hacerlo de nuevo.
- El script comprime el proyecto, lo sube por SCP y lo desempaqueta en `~/nivo_fx/`.

### 3. Servicios systemd instalados en Linux
Ambos servicios están creados, habilitados y corriendo en el Linux Mint:
- `nivo-dashboard.service` → Streamlit en `0.0.0.0:8501`
- `nivo-sentinel.service` → `quantum_engine/market_sentinel.py` headless

**Rutas en Linux:**
```
WorkingDirectory: /home/diego/nivo_fx/
Venv:             /home/diego/nivo_fx/.venv/
```

**Comandos de gestión en Linux:**
```bash
# Ver estado
sudo systemctl status nivo-dashboard.service
sudo systemctl status nivo-sentinel.service

# Reiniciar (después de un deploy)
sudo systemctl restart nivo-dashboard.service
sudo systemctl restart nivo-sentinel.service

# Ver logs en vivo
sudo journalctl -u nivo-dashboard.service -f
sudo journalctl -u nivo-sentinel.service -f
```

### 4. Dashboard accesible en red local
```
http://192.168.1.240:8501
```
Funciona desde cualquier dispositivo conectado a la misma red WiFi/LAN.

### 5. Dependencias instaladas en Linux venv
El primer `pip install -r requirements.txt` falló silenciosamente.  
**Fix confirmado:** Se instaló con `pip install --upgrade pip && pip install streamlit` primero, luego el resto.  
Estado actual: ✅ todas las dependencias instaladas y dashboard corriendo (`Active: running`, 38.4MB RAM).

---

## 🔲 Pendiente para la próxima sesión

### Notificaciones automáticas (Telegram Bot — GRATIS)
**Plan acordado:** Integrar un Telegram Bot en `market_sentinel.py` para enviar mensajes cuando:
1. Se genera una señal de trading (BUY/SELL)
2. El Guardian bloquea una operación
3. El sentinel se cae/reinicia (via systemd `OnFailure`)

**Pasos pendientes:**
1. El usuario crea un bot en Telegram con `@BotFather` → `/newbot` → obtiene TOKEN y chat_id
2. Se agrega función `send_telegram_alert(message)` en `market_sentinel.py` usando solo `requests` (ya instalado, sin dependencias extra)
3. Se integra en los puntos de decisión de `vm_executor.py`
4. Se hace un nuevo deploy con `deploy_to_linux.ps1`
5. Se reinician los servicios en Linux

**Nota importante:** No usar Twilio (de pago). Telegram Bot API es 100% gratuito y ya tenemos `requests` instalado.
