---
name: db_migration_manager
version: 1.0.0
description: "Safe evolution of data structures. Detect model changes and generate migration scripts automatically."
---

# [53] db_migration_manager
**Goal:** Safe evolution of data structures.

## Workflow
- **Detect Changes:** Detect changes in Python models (SQLAlchemy/Alembic).
- **Auto-Generate:** Generate migration scripts automatically.
- **Backup:** Create a database backup before applying migrations to the Finance App.

## Constraints
- Data loss during migration is unacceptable; always verify rollback capability.
