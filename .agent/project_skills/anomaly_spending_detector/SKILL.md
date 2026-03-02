---
name: anomaly_spending_detector
version: 1.0.0
description: "Scan the structured JSON ledger to identify duplicate charges, unusual spikes in spending, or recurring subscription patterns."
---

# ANOMALY SPENDING DETECTOR
**Objective:** Scan the structured JSON ledger to identify duplicate charges, unusual spikes in spending, or recurring subscription patterns.

## Instructions
1. **Input:** Receive the categorized JSON array of transactions.
2. **Duplicate Detection:** Scan for exact matches. IF two transactions have the exact same `date`, `charge` amount, and identical `description`, flag one as a potential duplicate.
3. **Subscription Detection:** Identify recurring patterns. IF a specific `description` (e.g., "NETFLIX", "SPOTIFY") appears multiple times with the exact same `charge` amount across different dates, flag it as a recurring subscription.
4. **Data Mutation:** Inject two new key-value pairs into every transaction object:
   - `"is_anomaly": boolean` (true if flagged, false otherwise).
   - `"anomaly_reason": string | null`.
5. **Output:** Return the finalized, enriched JSON array ready for database insertion and frontend rendering.

## Anomaly Reasons
- `Possible duplicate charge`
- `Recurring subscription detected`
- `None` (for non-anomalous items)
