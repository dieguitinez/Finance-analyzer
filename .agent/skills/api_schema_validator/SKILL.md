---
name: api_schema_validator
version: 1.0.0
description: "Ensuring stability across n8n and API integrations. Monitor JSON payloads and enforce Pydantic models."
---

# [52] api_schema_validator
**Goal:** Ensuring stability across n8n and API integrations.

## Workflow
- **Monitor Payloads:** Monitor incoming/outgoing JSON payloads.
- **Enforce Models:** Define and enforce Pydantic models for every external integration.
- **Drift Alert:** Alert if an external API changes its structure (Schema Drift).

## Constraints
- Log all validation errors with a full stack trace.
