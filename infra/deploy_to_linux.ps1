<#
.SYNOPSIS
    Deploys the Nivo FX Intelligence Suite to a remote Linux server.

.DESCRIPTION
    Compresses the local project (excluding .venv, caches, etc.), transfers via SCP,
    and executes targeted remote commands to unpack and restart services.
    .env files are uploaded SEPARATELY via SCP after the main archive.

.EXAMPLE
    .\deploy_to_linux.ps1 -RemoteUser "diego" -RemoteIP "192.168.1.240"
#>

Param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    [Parameter(Mandatory = $true)]
    [string]$RemoteIP,

    [string]$RemotePath = "~/nivo_fx"
)

$ScriptDir = Split-Path $PSScriptRoot -Parent
$ArchiveName = "nivo_deployment.tar.gz"
$SudoPass = "198824"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Nivo Intelligence Suite - Linux Deployer V2" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Target: $RemoteUser@$RemoteIP -> $RemotePath"
Write-Host ""

# ─── STEP 1: Cleanup old archives ────────────────────────────────────────────
if (Test-Path $ArchiveName) { Remove-Item $ArchiveName -Force }

# ─── STEP 2: Package project ─────────────────────────────────────────────────
Write-Host "[1/5] Packaging project (excluding .venv, __pycache__, etc.)..." -ForegroundColor Yellow
tar -czf $ArchiveName `
    --exclude="./.venv" `
    --exclude="./.local" `
    --exclude="./.agent" `
    --exclude="./.vscode" `
    --exclude="./.vscode-server" `
    --exclude="./.git" `
    --exclude="./*Backup" `
    --exclude="./archive" `
    --exclude="./venv~" `
    --exclude="./__pycache__" `
    --exclude="./*/__pycache__" `
    --exclude="./*/*/__pycache__" `
    --exclude="*.tar.gz" `
    --exclude="*.pyc" `
    -C "$ScriptDir" .

if (-not (Test-Path $ArchiveName)) {
    Write-Host "ERROR: Failed to create deployment archive." -ForegroundColor Red; exit 1
}
$SizeKB = [math]::Round((Get-Item $ArchiveName).Length / 1KB)
Write-Host "  -> Archive ready: $ArchiveName ($SizeKB KB)" -ForegroundColor Green

# ─── STEP 3: Upload the main archive ─────────────────────────────────────────
Write-Host "[2/5] Uploading main archive to $RemoteIP..." -ForegroundColor Yellow
scp $ArchiveName "${RemoteUser}@${RemoteIP}:${ArchiveName}"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: SCP transfer failed." -ForegroundColor Red; exit 1 }

# ─── STEP 4: Upload .env files SEPARATELY ────────────────────────────────────
Write-Host "[3/5] Uploading .env credential files..." -ForegroundColor Yellow
if (Test-Path "$ScriptDir\ai_stock_v2_institutional\.env") {
    scp "$ScriptDir\ai_stock_v2_institutional\.env" "${RemoteUser}@${RemoteIP}:nivo_stock_v2_env"
    Write-Host "  -> ai_stock_v2_institutional/.env uploaded" -ForegroundColor Green
} else { Write-Host "  [WARN] ai_stock_v2_institutional/.env not found locally." -ForegroundColor Yellow }

if (Test-Path "$ScriptDir\ai_forex_sentinel\.env") {
    scp "$ScriptDir\ai_forex_sentinel\.env" "${RemoteUser}@${RemoteIP}:nivo_forex_env"
    Write-Host "  -> ai_forex_sentinel/.env uploaded" -ForegroundColor Green
} else { Write-Host "  [WARN] ai_forex_sentinel/.env not found locally." -ForegroundColor Yellow }

# ─── STEP 5: Remote execution via a temp bash script ────────────────────────
# We write a bash script to a temp file to avoid PowerShell escaping issues with $, ||, etc.
Write-Host "[4/5] Executing remote setup script..." -ForegroundColor Yellow

# Write the bash script to a temp file on the LOCAL machine and upload it
$TmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
$BashScript = @'
#!/bin/bash
REMOTE_PATH="/home/diego/nivo_fx"
SUDO_PASS="198824"

echo "--- Unpacking archive ---"
mkdir -p $REMOTE_PATH
tar -xzf ~/nivo_deployment.tar.gz -C $REMOTE_PATH
rm -f ~/nivo_deployment.tar.gz

echo "--- Placing .env files ---"
[ -f ~/nivo_stock_v2_env ] && mv ~/nivo_stock_v2_env $REMOTE_PATH/ai_stock_v2_institutional/.env && echo "[OK] Stock V2 .env placed."
[ -f ~/nivo_forex_env ]    && mv ~/nivo_forex_env $REMOTE_PATH/ai_forex_sentinel/.env          && echo "[OK] Forex .env placed."

echo "--- Fixing shell script line endings ---"
find $REMOTE_PATH -maxdepth 3 -name "*.sh" -exec sed -i 's/\r$//' {} + 2>/dev/null || true

echo "--- Copying systemd service files (targeted, skips .venv) ---"
# NOTE: absolute path used here so sudo does not expand ~ as /root/
echo "$SUDO_PASS" | sudo -S sh -c "find $REMOTE_PATH/ai_forex_sentinel/services $REMOTE_PATH/ai_stock_v2_institutional/services -maxdepth 1 \( -name '*.service' -o -name '*.timer' \) -exec cp {} /etc/systemd/system/ \; 2>/dev/null || true"
echo "$SUDO_PASS" | sudo -S systemctl daemon-reload

echo "--- Enabling V2 services ---"
echo "$SUDO_PASS" | sudo -S systemctl enable nivo-stock-v2.service    2>/dev/null || true
echo "$SUDO_PASS" | sudo -S systemctl enable nivo-stock-tg-v2.service 2>/dev/null || true

echo "--- Restarting Nivo services ---"
for SVC in nivo-sentinel.timer nivo-sentinel.service nivo-stock-v2.service nivo-stock-tg-v2.service nivo-bot.service nivo-watchdog.service; do
    echo "$SUDO_PASS" | sudo -S systemctl restart $SVC 2>/dev/null && echo "  [OK] $SVC" || echo "  [SKIP] $SVC not found"
done

echo ""
echo "--- Final Service Status ---"
for SVC in nivo-sentinel.service nivo-stock-v2.service nivo-stock-tg-v2.service nivo-bot.service; do
    STATUS=$(systemctl is-active $SVC 2>/dev/null || echo "unknown")
    echo "  $SVC -> $STATUS"
done

echo ""
echo "==== DEPLOY COMPLETE ===="
'@

[System.IO.File]::WriteAllText($TmpScript, $BashScript, [System.Text.Encoding]::ASCII)

# Upload the script to remote
scp $TmpScript "${RemoteUser}@${RemoteIP}:nivo_deploy_script.sh"
Remove-Item $TmpScript -Force

# Execute it on the remote machine
ssh "${RemoteUser}@${RemoteIP}" "bash ~/nivo_deploy_script.sh; rm -f ~/nivo_deploy_script.sh"

# ─── STEP 6: Cleanup ─────────────────────────────────────────────────────────
Write-Host "[5/5] Cleaning up local temporary files..." -ForegroundColor Yellow
if (Test-Path $ArchiveName) { Remove-Item $ArchiveName -Force }

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " Deployment complete!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
