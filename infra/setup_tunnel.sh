#!/bin/bash
# ===========================================
#  Nivo FX - Cloudflare Tunnel Setup v2
#  - Instala cloudflared
#  - Crea servicio del tunnel
#  - Extrae la URL publica y la guarda en .env
#  - El bot usara esa URL en cada alerta
# ===========================================

set -e

ENV_FILE="/home/diego/nivo_fx/.env"
SERVICE_FILE="/etc/systemd/system/nivo-tunnel.service"
EXTRACT_SCRIPT="/home/diego/nivo_fx/get_tunnel_url.sh"

echo "=== Nivo FX - Cloudflare Tunnel Setup ==="

# 1. Instalar cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "[1/5] Instalando cloudflared..."
    curl -L --output /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
    echo "    OK: cloudflared instalado."
else
    echo "[1/5] cloudflared ya instalado."
fi

# 2. Crear script que extrae y guarda la URL del tunnel
echo "[2/5] Creando script extractor de URL..."
cat > "$EXTRACT_SCRIPT" << 'EXTRACTEOF'
#!/bin/bash
# Espera a que el tunnel genere la URL y la guarda en .env
ENV_FILE="/home/diego/nivo_fx/.env"
LOG_FILE="/tmp/nivo_tunnel.log"
MAX_WAIT=30
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if [ -f "$LOG_FILE" ]; then
        URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG_FILE" | tail -1)
        if [ -n "$URL" ]; then
            # Actualizar o agregar DASHBOARD_URL en .env
            if grep -q "^DASHBOARD_URL=" "$ENV_FILE"; then
                sed -i "s|^DASHBOARD_URL=.*|DASHBOARD_URL=\"$URL\"|" "$ENV_FILE"
            else
                echo "DASHBOARD_URL=\"$URL\"" >> "$ENV_FILE"
            fi
            echo "URL guardada: $URL"
            # Reiniciar el bot para que lea la nueva URL (ignoramos error)
            sudo systemctl restart nivo-bot.service 2>/dev/null || true
            exit 0
        fi
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done
echo "No se pudo extraer la URL del tunnel."
EXTRACTEOF
chmod +x "$EXTRACT_SCRIPT"

# 3. Crear servicio systemd para el tunnel
echo "[3/5] Creando servicio del tunnel..."
sudo tee "$SERVICE_FILE" > /dev/null << 'EOF'
[Unit]
Description=Nivo FX Cloudflare Tunnel
After=network.target

[Service]
User=diego
ExecStartPre=-/usr/bin/pkill -f cloudflared
ExecStartPre=-/bin/bash -c "rm -f /tmp/nivo_tunnel.log"
ExecStart=/bin/bash -c "/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8501 2>&1 | tee /tmp/nivo_tunnel.log"
ExecStartPost=-/bin/bash /home/diego/nivo_fx/get_tunnel_url.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 4. Activar y arrancar el tunnel
echo "[4/5] Activando el tunnel..."
sudo pkill -f cloudflared || true
sudo systemctl daemon-reload
sudo systemctl enable nivo-tunnel.service
sudo systemctl restart nivo-tunnel.service

# 5. Esperar y mostrar resultado
echo "[5/5] Esperando URL del tunnel..."
sleep 8
URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/nivo_tunnel.log 2>/dev/null | tail -1)

echo ""
echo "============================================"
if [ -n "$URL" ]; then
    echo " Dashboard disponible en:"
    echo " $URL"
    echo "============================================"
    echo ""
    echo " Esta URL se guarda en .env automaticamente."
    echo " Cada alerta de Telegram incluira este link."
else
    echo " Tunnel iniciado. Revisa /tmp/nivo_tunnel.log"
    echo "============================================"
fi
