---
name: tdd_sentinel
version: 1.0.0
description: "Enforce Test-Driven Development protocol. Scan codebase, generate pytest files, and ensure Fail (Red) -> Pass (Green) workflow."
---

# [46] tdd_sentinel
**Goal:** Enforce Test-Driven Development.

## Workflow
- **Scan codebase:** Identify new logic requiring test coverage.
- **Generate pytest files:** Create tests covering edge cases *before* implementation.
- **Test Cycle:** Proceed only if tests fail initially (Red phase) and then pass (Green phase).

## Constraints
- No code shall be merged without 90%+ branch coverage.
