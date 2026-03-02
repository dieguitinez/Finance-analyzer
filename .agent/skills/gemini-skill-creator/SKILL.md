---
name: creating-gemini-skills
description: Generates high-quality, predictable, and efficient .agent/skills/ directories based on user requirements. Use when the user asks to create a new skill or automate a specific workflow.
---

# Gemini Skill Creator

## When to use this skill

- When requested to create a new "Skill" for the Antigravity agent environment.
- When the user wants to automate a specific task using a structured skill format.
- Use when keywords like "create skill", "build skill", or "skill creator" are mentioned.

## Workflow

- [ ] Understand user requirements for the new skill.
- [ ] Define the skill name (gerund-name) and description (3rd-person).
- [ ] Create the folder hierarchy: `.agent/skills/<skill-name>/`.
- [ ] Generate `SKILL.md` with appropriate YAML frontmatter and content.
- [ ] (Optional) Create `scripts/`, `examples/`, or `resources/` if needed.
- [ ] Validate the skill by providing a usage example.

## Instructions

### 1. Core Structural Requirements

Every skill must follow this folder hierarchy:

- `<skill-name>/`
  - `SKILL.md` (Required: Main logic and instructions)
  - `scripts/` (Optional: Helper scripts)
  - `examples/` (Optional: Reference implementations)
  - `resources/` (Optional: Templates or assets)

### 2. YAML Frontmatter Standards

The `SKILL.md` must start with YAML frontmatter following these strict rules:

- **name**: Gerund form (e.g., `testing-code`, `managing-databases`). Max 64 chars. Lowercase, numbers, and hyphens only. No "claude" or "anthropic" in the name.
- **description**: Written in **third person**. Must include specific triggers/keywords. Max 1024 chars.

### 3. Writing Principles

- **Conciseness**: Assume the agent is smart. Focus only on the unique logic of the skill.
- **Progressive Disclosure**: Keep `SKILL.md` under 500 lines. Use secondary files for more detail.
- **Forward Slashes**: Always use `/` for paths.
- **Degrees of Freedom**:
  - Use **Bullet Points** for high-freedom tasks.
  - Use **Code Blocks** for medium-freedom.
  - Use **Specific Bash Commands** for low-freedom.

### 4. Workflow & Feedback Loops

- Include **Checklists** for state tracking.
- Use **Validation Loops** (Plan-Validate-Execute).
- Instructions for scripts should be "black boxes" (run `--help` if unsure).

## Resources

- [.agent/skills/](file:///c:/Users/qqqq/Pictures/Screenshots/SkillsAG/.agent/skills/)
