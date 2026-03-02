---
name: env_config_guard
version: 1.0.0
description: "Zero-leak credential security. Scan for hardcoded keys, maintain templates, and ensure gitignore compliance."
---

# [54] env_config_guard
**Goal:** Zero-leak credential security.

## Workflow
- **Secret Scanning:** Scan all files for hardcoded API keys or secrets.
- **Template Maintenance:** Maintain `.env.template` with all required keys for Nivo Partners' services.
- **Gitignore Compliance:** Ensure `.gitignore` correctly excludes all sensitive configuration files.

## Constraints
- Immediate block on any commit containing a detected secret.
