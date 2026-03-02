---
name: pii_data_sanitizer
version: 1.0.0
description: "Intercept raw document data in memory and redact Personally Identifiable Information (PII) before any downstream processing."
---

# PII DATA SANITIZER
**Objective:** Intercept raw document data in memory and redact Personally Identifiable Information (PII) before any downstream processing or database insertion occurs.

## Instructions
1. **Scan input:** Scan raw text/vision input for standard banking PII patterns.
2. **Redact entities:**
   - **Account Numbers:** Any contiguous string of 8 to 18 digits. Replace with `[REDACTED_ACCOUNT]`.
   - **Routing Numbers / Swift Codes:** Replace with `[REDACTED_ROUTING]`.
   - **Holder Info:** Primary Account Holder Name and physical addresses (usually found at top of first page). Replace with `[REDACTED_HOLDER_INFO]`.
3. **CRITICAL EXCEPTION:** Do NOT redact transaction descriptions. Merchant names, store locations (e.g., "Starbucks Miami"), and transaction reference IDs must remain intact for analysis.
4. **Output:** Pass sanitized raw text block to the next agent node.

## Constraints
- No unredacted PII should persist after this node.
- Financial integrity of transaction data must be preserved.
