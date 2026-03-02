#!/bin/bash
# Nivo FX - Setup Daily/Weekly Automation
# Usage: bash scripts/setup_cron.sh

echo "============================================="
echo " Configuring Nivo FX Automatic Maintenance"
echo "============================================="

# Get absolute path to the clean_logs script
PROJECT_DIR=$(pwd)
CLEAN_SCRIPT="$PROJECT_DIR/scripts/clean_logs.sh"

if [ ! -f "$CLEAN_SCRIPT" ]; then
    echo "ERROR: Could not find clean_logs.sh at $CLEAN_SCRIPT"
    exit 1
fi

# Make it executable
chmod +x "$CLEAN_SCRIPT"

# Add to crontab (Run every Sunday at 00:00)
# Format: min hour day month weekday command
(crontab -l 2>/dev/null; echo "0 0 * * 0 /bin/bash $CLEAN_SCRIPT > /dev/null 2>&1") | crontab -

echo "SUCCESS: Cron job scheduled!"
echo "The system will now automatically clean logs and cache every Sunday at midnight."
echo "============================================="
crontab -l | grep "clean_logs.sh"
echo "============================================="
