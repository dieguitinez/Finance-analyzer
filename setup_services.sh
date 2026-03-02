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
SERVICES=("nivo-bot.service" "nivo-sentinel.service")
TIMER="nivo-sentinel.timer"

echo "🎯 Starting Nivo FX Service Setup..."

# 1. Enter project directory
cd "$PROJECT_DIR"

# 2. Fix permissions (Ensure diego owns everything)
echo "🔧 Setting permissions..."
sudo chown -R diego:diego "$PROJECT_DIR"

# 3. Install Systemd Services
for SERVICE in "${SERVICES[@]}"; do
    if [ -f "$SERVICE" ]; then
        echo "📂 Installing $SERVICE..."
        sudo cp "$SERVICE" "/etc/systemd/system/"
    else
        echo "⚠️ Warning: $SERVICE not found in root."
    fi
done

# 4. Install Timer
if [ -f "$TIMER" ]; then
    echo "📂 Installing $TIMER..."
    sudo cp "$TIMER" "/etc/systemd/system/"
fi

# 5. Reload and Restart
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ Enabling Telegram Bot..."
sudo systemctl enable --now nivo-bot.service

echo "✅ Enabling Sentinel Timer (1min cycles)..."
sudo systemctl enable --now nivo-sentinel.timer

echo "📊 Current Status:"
sudo systemctl status nivo-bot.service --no-pager | grep "Active:"
sudo systemctl status nivo-sentinel.timer --no-pager | grep "Active:"

echo ""
echo "========================================================"
echo "  Nivo FX Services are ACTIVE and monitoring the market."
echo "========================================================"
