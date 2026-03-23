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
