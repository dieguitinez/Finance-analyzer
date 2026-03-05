#!/bin/bash
# Nivo - Master Cleanup: Forex Bot + Stock Sentinel
# Corre automaticamente a medianoche via cron (setup_cron.sh)
# Uso manual: bash scripts/clean_logs.sh

echo "============================================="
echo " Nivo - Master System Deep Cleanup"
echo "    Forex Bot (OANDA) + Stock Sentinel (Alpaca)"
echo "============================================="

# 1. Systemd Journals (aplica a AMBOS bots)
echo "[1/7] Restringiendo logs del sistema a 1 dia / 100MB..."
sudo journalctl --vacuum-time=1d
sudo journalctl --vacuum-size=100M

# 2. APT Package Cleanup
echo "[2/7] Limpiando caches de APT y paquetes viejos..."
sudo apt-get clean
sudo apt-get autoremove -y --purge

# 3. Logs comprimidos del sistema
echo "[3/7] Eliminando logs comprimidos en /var/log..."
sudo find /var/log -type f -name "*.gz" -delete
sudo find /var/log -type f -name "*.1" -delete

# 4. Thumbnail Cache
echo "[4/7] Limpiando caches de miniaturas..."
rm -rf ~/.cache/thumbnails/*

# 5. Python bytecode
echo "[5/7] Removiendo bytecode Python y caches temporales..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# ─────────────────────────────────────────────
# 6. FOREX BOT (OANDA) - archivos temporales
# ─────────────────────────────────────────────
echo "[6/7] Limpiando archivos temporales del Forex Bot (OANDA)..."
rm -f nohup.out
rm -f *.tar.gz
rm -f *.log
rm -f /tmp/lstm_training.log        # Log de entrenamiento LSTM (puede ser grande)
rm -f /tmp/nivo_open_positions.json # Cache de posiciones abiertas

# ─────────────────────────────────────────────
# 7. STOCK SENTINEL (Alpaca) - archivos temporales
# ─────────────────────────────────────────────
echo "[7/7] Limpiando archivos temporales del Stock Sentinel (Alpaca)..."
rm -f ai_stock_sentinel/*.log*         # Logs rotativos (sentinel.log*)
rm -f /tmp/nivo_stock_queue.json       # Cola de ordenes nocturnas persistida

echo "============================================="
echo " Cleanup Completo. Uso de disco actualizado:"
df -h | grep '^/dev/'
echo "============================================="
echo " Forex Bot:  logs systemd + /tmp/lstm_training.log"
echo " Stock Sentinel: ai_stock_sentinel/*.log + /tmp/nivo_stock_queue.json"
echo "============================================="
