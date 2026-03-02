---
name: planning-work-skills
description: Creates comprehensive implementation plans for complex tasks. Use when a design is approved and needs to be broken down into actionable steps.
---

# Planning Work Skills

## When to use this skill

- When an implementation plan is needed for a new feature or fix.
- When complex changes affect multiple files or components.
- When a task needs to be delegated or documented clearly.

## Workflow

- [ ] Analyze the approved design or requirements.
- [ ] Identify all affected files and components.
- [ ] Break down the work into bite-sized tasks (2-5 minutes each).
- [ ] Specify exact file paths and line ranges where applicable.
- [ ] Include code snippets or detailed logic changes for each task.
- [ ] Define verification steps (tests, commands, manual checks).

## Instructions

### 1. Zero Context Principle

Write the plan as if the engineer has zero context for the codebase. Document everything necessary to complete the task without external research.

### 2. Task Granularity

Each task should be self-contained and achievable in a short duration. This allows for frequent commits and easier progress tracking.

### 3. Verification First

Every task must have a corresponding verification step. Emphasize Test-Driven Development (TDD) principles where possible.

### 4. Code Standards

Adhere to DRY (Don't Repeat Yourself) and YAGNI (You Ain't Gonna Need It) principles. Ensure the proposed code has high quality and matches existing project standards.

## Resources

- [.agent/skills/](file:///c:/Users/qqqq/Pictures/Screenshots/SkillsAG/.agent/skills/)
