---
name: ledger_math_auditor
version: 1.0.0
description: "Cryptographically and mathematically verify the accuracy of the extracted JSON payload against the statement's summary."
---

# LEDGER MATH AUDITOR
**Objective:** Cryptographically and mathematically verify the accuracy of the extracted JSON payload against the statement's summary.

## Instructions

1. **IDENTIFY BALANCES:** Identify the "Beginning Balance" and "Ending Balance" explicitly stated in the document summary section.
2. **PARSE PAYLOAD:** Parse the incoming JSON array of transactions.
3. **INITIATE AUDIT:** Establish a `Running Balance` variable starting with the "Beginning Balance".
4. **ITERATE & CALCULATE:**
   - Iterate chronologically through the JSON array.
   - For every `charge`, subtract from `Running Balance`.
   - For every `deposit`, add to `Running Balance`.
5. **VALIDATION CHECK:** Compare final calculated `Running Balance` with the document's stated "Ending Balance".
   - **SUCCESS:** If they match, pass the JSON payload forward as `PRODUCTION_READY`.
   - **FAILURE:** If they do not match (Discrepancy > 0.00), trigger a `RETRY_EXTRACTION` flag. Log the exact row where the math broke down to force re-evaluation of bounding boxes.

## Constraints
- Zero tolerance for discrepancies.
- Must provide exact error context for retries.
