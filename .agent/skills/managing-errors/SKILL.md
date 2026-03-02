---
name: managing-errors
description: Master error handling patterns across languages to build resilient applications. Use when implementing error handling, designing APIs, or improving application reliability.
---

# Managing Errors

Build resilient applications with robust error handling strategies that gracefully handle failures and provide excellent debugging experiences.

## When to use this skill

- Implementing error handling in new features.
- Designing error-resilient APIs.
- Debugging production issues or improving application reliability.
- Creating better error messages for users and developers.
- Implementing retry, circuit breaker, or graceful degradation patterns.

## Workflow

- [ ] Identify the category of error (Recoverable vs Unrecoverable).
- [ ] Choose the appropriate philosophy (Exceptions vs Result Types).
- [ ] Implement language-specific patterns (Python, TS, Rust, Go).
- [ ] Apply universal patterns (Circuit Breaker, Aggregation, Fallback).
- [ ] Validate with the "Best Practices" checklist.

## Core Concepts

### 1. Error Handling Philosophies

- **Exceptions**: Traditional try-catch, disrupts control flow. Use for unexpected/exceptional conditions.
- **Result Types**: Explicit success/failure, functional approach. Use for expected errors/validation.
- **Error Codes**: C-style, requires discipline.
- **Option/Maybe**: For nullable values.

### 2. Error Categories

- **Recoverable**: Network timeouts, missing files, invalid input, rate limits.
- **Unrecoverable**: Out of memory, stack overflow, programming bugs (null pointer).

## Language-Specific Patterns

### Python

- **Exception Hierarchy**: Use a base `ApplicationError` class.
- **Context Managers**: Use `@contextmanager` for cleanup (e.g., DB transactions).
- **Retry Logic**: Use decorators with exponential backoff.

### TypeScript/JavaScript

- **Custom Error Classes**: Extend `Error` with `code` and `statusCode`.
- **Result Type Pattern**: Define `type Result<T, E> = { ok: true; value: T } | { ok: false; error: E }`.
- **Async Handling**: Proper `try/catch` around `await` or `.catch()` on promises.

### Rust

- **Result & Option**: Leverage `?` operator for propagation.
- **Custom Enums**: Use `derive(Debug)` and `impl From<T>` for error conversion.

### Go

- **Explicit Returns**: `if err != nil { return nil, fmt.Errorf(...) }`.
- **Sentinel Errors**: Define `var ErrNotFound = errors.New(...)`.
- **Error Wrapping**: Use `%w` in `fmt.Errorf` and `errors.Is`/`errors.As` for checking.

## Universal Patterns

### 1. Circuit Breaker

Prevent cascading failures by rejecting requests when a service is failing. States: `CLOSED`, `OPEN`, `HALF_OPEN`.

### 2. Error Aggregation

Collect multiple errors (e.g., form validation) instead of failing on the first one.

### 3. Graceful Degradation

Provide fallback functionality (e.g., cache) when the primary service fails.

## Best Practices Checklist

- [ ] **Fail Fast**: Validate input early.
- [ ] **Preserve Context**: Include stack traces, metadata, timestamps.
- [ ] **Meaningful Messages**: Explain what happened and how to fix it.
- [ ] **Clean Up**: Use try-finally, context managers, or `defer`.
- [ ] **Don't Swallow Errors**: Log or re-throw; never silently ignore.

## Resources

- [.agent/skills/](file:///c:/Users/qqqq/Pictures/Screenshots/SkillsAG/.agent/skills/)
