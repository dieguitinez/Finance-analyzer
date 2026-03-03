#!/bin/bash
# Nivo FX Master Cleanup: High-Efficiency Disk Space Recovery
# Targets sda2 (root) and sda3 (home)
# Usage: bash scripts/clean_logs.sh

echo "============================================="
echo " 🔥 Nivo FX - Master System Deep Cleanup 🔥"
echo "============================================="

# 1. Vacuum Systemd Journals (Legacy logs)
echo "[1/6] Restricting system logs to 1 day / 100MB..."
sudo journalctl --vacuum-time=1d
sudo journalctl --vacuum-size=100M

# 2. APT Package Cleanup (Frees space on sda2)
echo "[2/6] Cleaning up APT caches and old packages..."
sudo apt-get clean
sudo apt-get autoremove -y --purge

# 3. Old Log Files Cleanup (Frees space on sda2)
echo "[3/6] Deleting rotated/compressed logs in /var/log..."
sudo find /var/log -type f -name "*.gz" -delete
sudo find /var/log -type f -name "*.1" -delete

# 4. Thumbnail Cache Cleanup (Frees space on sda3)
echo "[4/6] Clearing persistent thumbnail caches..."
rm -rf ~/.cache/thumbnails/*

# 5. Project Cache Cleanup
echo "[5/6] Removing Python bytecode and temporary caches..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 6. Deployment & Log Artifact Cleanup
echo "[6/6] Removing old deployment archives and heavy root logs..."
rm -f *.tar.gz
rm -f nohup.out
rm -f *.log
rm -f ai_stock_sentinel/*.log*

echo "============================================="
echo " ✅ Cleanup Complete. Updated Disk Usage:"
df -h | grep '^/dev/'
echo "============================================="
