#!/bin/bash
# ========================================================
# Nivo FX - Remote Service Setup Routine
# Target: Linux Server (diego@192.168.1.240)
# ========================================================

set -e

# Prevencion de errores por line endings de Windows
if command -v sed &> /dev/null; then
  find . -type f -name "*.sh" -exec sed -i 's/\r$//' {} +
  find . -type f -name "*.service" -exec sed -i 's/\r$//' {} +
  find . -type f -name "*.timer" -exec sed -i 's/\r$//' {} +
fi

PROJECT_DIR="/home/diego/nivo_fx"
SERVICES=("nivo-sentinel.service" "nivo-bot.service" "stock-watcher.service" "stock-bot-tg.service" "nivo-watchdog.service")
TIMERS=("nivo-sentinel.timer")

echo "🎯 Starting Nivo FX Service Setup..."

# 1. Enter project directory
cd "$PROJECT_DIR"

# 2. Fix permissions (Ensure diego owns everything)
echo "🔧 Setting permissions..."
sudo chown -R diego:diego "$PROJECT_DIR"

# 3. Install Systemd Services (Check Silos)
SOURCE_FOLDERS=("ai_forex_sentinel/services" "ai_stock_sentinel/services")

for SERVICE in "${SERVICES[@]}"; do
    FOUND=false
    for FOLDER in "${SOURCE_FOLDERS[@]}"; do
        if [ -f "$FOLDER/$SERVICE" ]; then
            echo "✅ Installing $SERVICE from $FOLDER..."
            sudo cp "$FOLDER/$SERVICE" "/etc/systemd/system/"
            FOUND=true
            break
        fi
    done
    if [ "$FOUND" = false ]; then
        echo "⚠️ Warning: $SERVICE not found in any service folder."
    fi
done

# 4. Install Timers (Check Silos)
for TIMER in "${TIMERS[@]}"; do
    FOUND=false
    for FOLDER in "${SOURCE_FOLDERS[@]}"; do
        if [ -f "$FOLDER/$TIMER" ]; then
            echo "✅ Installing $TIMER from $FOLDER..."
            sudo cp "$FOLDER/$TIMER" "/etc/systemd/system/"
            FOUND=true
            break
        fi
    done
    if [ "$FOUND" = false ]; do
        echo "⚠️ Warning: $TIMER not found in any service folder."
    fi
done

# 5. Reload and Restart
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ Enabling Telegram Bot..."
sudo systemctl enable --now nivo-bot.service

echo "✅ Enabling Sentinel Timer (1min cycles)..."
sudo systemctl enable --now nivo-sentinel.timer

echo "🚀 Enabling Watchdog service..."
sudo systemctl enable --now nivo-watchdog.service

echo "🚀 Restarting Stock Bot services..."
sudo systemctl restart stock-watcher.service
sudo systemctl restart stock-bot-tg.service

echo "⚡ Current Status:"
sudo systemctl status nivo-bot.service --no-pager | grep "Active:"
sudo systemctl status nivo-sentinel.timer --no-pager | grep "Active:"

echo ""
echo "========================================================"
echo "  Nivo FX Services are ACTIVE and monitoring the market."
echo "========================================================"
