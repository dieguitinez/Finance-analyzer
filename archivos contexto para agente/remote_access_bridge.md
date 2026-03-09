# Nivo FX - Connection Bridge & Secure Access

**Date:** March 6, 2026

This document is intended for future AI agents to gain secure access to the Nivo Linux Server for maintenance, deployment, and status checks.

## 1. SSH Access (Passwordless)

The server can be accessed directly via SSH without typing the user password manually. This is handled by the local SSH configuration on the host machine.

- **User:** `diego`
- **Host:** `192.168.1.240`
- **Identity:** The `~/.ssh/config` file in the user's home directory (`C:\Users\qqqq\.ssh\config`) is set to automatically use the correct key and agent forwarding.
- **Access Rule:** Simply use `ssh diego@192.168.1.240` or the command tool to run remote tasks. No key path is needed as it is pre-configured.

## 2. Sudo Privileges & Service Control

While passwordless `sudo` is not enabled, the `sudo` password has been provided by the user in a safe manner during this session.

- **Sudo Password (Masked Logic):** To perform restricted operations (systemctl restarts, editing systemd files), use the following pattern:

  ```bash
  echo "198824" | sudo -S <command>
  ```

- **Usage Example:** `echo "198824" | sudo -S systemctl restart stock-watcher`

## 3. Git Operations

When performing `git push` or `git pull` from the Linux server, the current agent setup uses the same SSH relay. If an agent needs to push changes from the server, ensure it is within the `/home/diego/nivo_fx/` directory and use standard git commands via the SSH bridge.

## 4. Environment Files

Sensitive credentials (API keys) are stored in `.env` files which are **strictly ignored** by Git.

- **Location:**
  - Forex Bot: `/home/diego/nivo_fx/.env`
  - Stock Bot: `/home/diego/nivo_fx/ai_stock_sentinel/.env`

*Do not commit these files or reveal the full keys in public logs.*
