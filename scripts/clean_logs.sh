#!/bin/bash
# Nivo FX Maintenance Script: Disk Space & Log Rotation
# Usage: bash scripts/clean_logs.sh

echo "============================================="
echo " Nivo FX - Linux Maintenance & Disk Cleanup"
echo "============================================="

# 1. Systemd Journal Vacuuming (Limit logs to 7 days or 500MB)
echo "[1/3] Vacuuming systemd journals..."
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=500M

# 2. Project Cache Cleanup
echo "[2/3] Removing Python bytecode and temporary caches..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name "*.egg-info" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 3. Deployment Artifact Cleanup
echo "[3/3] Removing old deployment archives..."
rm -f *.tar.gz

echo "============================================="
echo " Maintenance Complete. Current Disk Usage:"
df -h | grep '^/dev/'
echo "============================================="
