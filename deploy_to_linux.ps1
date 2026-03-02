<#
.SYNOPSIS
    Deploys the Nivo FX Intelligence Suite from a Windows local machine to a remote Linux Mint server.

.DESCRIPTION
    This script compresses the local project directory (excluding heavy virtual environments
    and cache files) and transfers it securely to the Linux server using SCP (Secure Copy Protocol).
    Then, it executes remote SSH commands to unpack the files and set them up in the correct location.

.PARAMETER RemoteUser
    The username on the Linux Mint server (e.g., 'ubuntu', 'root', or your specific username).

.PARAMETER RemoteIP
    The IP address of the Linux Mint server (e.g., '192.168.1.100').

.PARAMETER RemotePath
    The destination folder path on the Linux server (default: '~/nivo_fx').

.EXAMPLE
    .\deploy_to_linux.ps1 -RemoteUser "tu_usuario" -RemoteIP "192.168.1.50"
#>

Param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    [Parameter(Mandatory = $true)]
    [string]$RemoteIP,

    [string]$RemotePath = "~/nivo_fx"
)

$ScriptDir = $PSScriptRoot
$ArchiveName = "nivo_deployment.tar.gz"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Nivo FX Intelligence Suite - Linux Deployer" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Target Server: $RemoteUser@$RemoteIP"
Write-Host "Target Path: $RemotePath"
Write-Host ""

# 1. Clean up old archives
if (Test-Path $ArchiveName) {
    Remove-Item $ArchiveName -Force
}

# 2. Package the project (Excluding .venv to prevent Windows/Linux binary conflicts)
Write-Host "[1/4] Packaging project for deployment (Excluding .venv)..." -ForegroundColor Yellow
tar -czf $ArchiveName --exclude='.venv' --exclude='__pycache__' --exclude='.git' --exclude='*.tar.gz' -C $ScriptDir .

if (-not (Test-Path $ArchiveName)) {
    Write-Host "Error: Failed to create deployment archive." -ForegroundColor Red
    exit 1
}

# 3. Transfer the archive securely via SCP
Write-Host "[2/4] Uploading to Linux server ($RemoteIP)..." -ForegroundColor Yellow
Write-Host "You may be prompted for the SSH password of user '$RemoteUser'."
scp $ArchiveName "${RemoteUser}@${RemoteIP}:${ArchiveName}"

# 4. Remote execution: Unpack and Setup
Write-Host "[3/4] Unpacking and setting up remotely..." -ForegroundColor Yellow
$RemoteCommands = @"
mkdir -p $RemotePath
tar -xzf $ArchiveName -C $RemotePath
rm -f $ArchiveName
echo '---- Deployment Unpacked Successfully ----'
"@

# Fix line endings (\r\n -> \n) for Linux compatibility
$CleanCommands = $RemoteCommands -replace "`r", ""

ssh "${RemoteUser}@${RemoteIP}" $CleanCommands

# 5. Cleanup local build
Write-Host "[4/4] Cleaning up local temporary files..." -ForegroundColor Yellow
Remove-Item $ArchiveName -Force

Write-Host "=============================================" -ForegroundColor Green
Write-Host " Deployment package transferred and unpacked!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host "Remember to restart the systemd services on Linux if they are already running:"
Write-Host "  sudo systemctl restart nivo-dashboard.service"
Write-Host "  sudo systemctl restart nivo-sentinel.service"
