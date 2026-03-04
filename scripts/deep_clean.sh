#!/bin/bash
# =====================================================
#   Nivo - Deep Clean Ubuntu
#   Limpieza profunda del laptop Linux
#   Uso: bash scripts/deep_clean.sh
#   Seguro para correr cuando quieras recuperar espacio
# =====================================================

echo ""
echo "================================================"
echo "   NIVO DEEP CLEAN — Ubuntu System Scrubber"
echo "   Forex Bot + Stock Sentinel + Sistema General"
echo "================================================"
echo ""

# Mostrar espacio ANTES
echo ">>> Espacio ANTES de la limpieza:"
df -h | grep '^/dev/'
echo ""

# ─────────────────────────────────────────────────────
# BLOQUE 1 — BOTS (Nivo FX + Stock Sentinel)
# ─────────────────────────────────────────────────────
echo "[ BOT 1 ] Limpiando Forex Bot (OANDA)..."
rm -f nohup.out *.tar.gz
rm -f /tmp/lstm_training.log
rm -f /tmp/nivo_open_positions.json

echo "[ BOT 2 ] Limpiando Stock Sentinel (Alpaca)..."
rm -f ai_stock_sentinel/*.log*
rm -f /tmp/nivo_stock_queue.json

echo "[ BOTS  ] Limpiando bytecode Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# ─────────────────────────────────────────────────────
# BLOQUE 2 — SISTEMA GENERAL
# ─────────────────────────────────────────────────────
echo ""
echo "[ SYS 1 ] Logs del sistema (journalctl)..."
sudo journalctl --vacuum-time=2d
sudo journalctl --vacuum-size=50M

echo "[ SYS 2 ] APT — paquetes huerfanos y cache..."
sudo apt-get clean -y
sudo apt-get autoclean -y
sudo apt-get autoremove -y --purge

echo "[ SYS 3 ] Kernels viejos (guarda los 2 mas recientes)..."
sudo dpkg -l 'linux-image-[0-9]*' | awk '/^ii/{print $2}' | \
    sort -V | head -n -2 | \
    xargs --no-run-if-empty sudo apt-get purge -y 2>/dev/null || true

echo "[ SYS 4 ] Logs comprimidos en /var/log..."
sudo find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null
sudo truncate -s 0 /var/log/syslog 2>/dev/null || true
sudo truncate -s 0 /var/log/auth.log 2>/dev/null || true

echo "[ SYS 5 ] Archivos /tmp mas viejos de 1 dia..."
sudo find /tmp -mindepth 1 -mtime +1 -delete 2>/dev/null
sudo find /var/tmp -mindepth 1 -mtime +7 -delete 2>/dev/null

echo "[ SYS 6 ] Crash reports y core dumps..."
sudo rm -rf /var/crash/* 2>/dev/null
sudo rm -rf /var/lib/systemd/coredump/* 2>/dev/null
rm -rf ~/.local/share/recently-used.xbel 2>/dev/null

echo "[ SYS 7 ] Snaps viejos (guarda la version actual)..."
snap list --all 2>/dev/null | awk '/disabled/{print $1, $3}' | \
    while read snapname revision; do
        sudo snap remove "$snapname" --revision="$revision" 2>/dev/null
    done

# ─────────────────────────────────────────────────────
# BLOQUE 3 — CACHES DE USUARIO
# ─────────────────────────────────────────────────────
echo ""
echo "[ USR 1 ] Cache de miniaturas..."
rm -rf ~/.cache/thumbnails/*

echo "[ USR 2 ] Cache general (~/.cache) — excepto pip y venv..."
find ~/.cache -mindepth 1 -maxdepth 1 \
    ! -name "pip" \
    ! -name ".venv" \
    -exec rm -rf {} + 2>/dev/null

echo "[ USR 3 ] pip cache..."
pip cache purge 2>/dev/null || true

echo "[ USR 4 ] Papelera..."
rm -rf ~/.local/share/Trash/files/* 2>/dev/null
rm -rf ~/.local/share/Trash/info/* 2>/dev/null

echo "[ USR 5 ] Cache de Firefox (si existe)..."
rm -rf ~/.cache/mozilla/firefox/*/cache2 2>/dev/null

echo "[ USR 6 ] Cache de Chrome/Chromium (si existe)..."
rm -rf ~/.cache/google-chrome/Default/Cache 2>/dev/null
rm -rf ~/.cache/chromium/Default/Cache 2>/dev/null

# ─────────────────────────────────────────────────────
# BLOQUE 4 — MEMORIA (libera cache del kernel)
# ─────────────────────────────────────────────────────
echo ""
echo "[ MEM  ] Liberando cache de paginas del kernel..."
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

# ─────────────────────────────────────────────────────
# RESUMEN FINAL
# ─────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "   LIMPIEZA COMPLETA. Espacio DESPUES:"
df -h | grep '^/dev/'
echo "================================================"
echo ""
echo "  Bots limpiados:"
echo "    - Forex (OANDA):    logs + /tmp/*.json"
echo "    - Stock Sentinel:   sentinel.log* + queue.json"
echo ""
echo "  Sistema limpiado:"
echo "    - journalctl / APT / kernels viejos / /var/log"
echo "    - /tmp (>1 dia) / /var/tmp (>7 dias)"
echo "    - Crash reports / Snaps disabled"
echo "    - ~/.cache / pip / papelera / browsers"
echo "    - Kernel page cache (sync + drop_caches)"
echo "================================================"
