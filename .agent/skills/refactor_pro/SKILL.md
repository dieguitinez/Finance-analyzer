---
name: refactor_pro
version: 1.0.0
description: "Technical debt mitigation. Identify code smells and propose refactoring based on SOLID/DRY principles."
---

# [50] refactor_pro
**Goal:** Technical debt mitigation.

## Workflow
- **Identify Smells:** Detect large classes, deeply nested loops, and repetitive code.
- **Propose Refactor:** Propose changes based on SOLID and DRY principles.
- **Verification:** Implement changes only if `tdd_sentinel` confirms no regressions.

## Constraints
- Performance must remain stable or improve after refactoring.
