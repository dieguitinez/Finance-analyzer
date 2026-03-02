---
name: regex_financial_extractor
version: 1.0.0
description: "Parse, clean, and normalize messy string data from the ledger into standardized programming data types (ISO dates, float amounts, etc.)."
---

# REGEX FINANCIAL EXTRACTOR
**Objective:** Parse, clean, and normalize messy string data from the ledger into standardized programming data types.

## Instructions

1. **DATE NORMALIZATION:**
   - Detect date strings in any format (e.g., "12/Feb", "02-12-2026", "12/02", "Feb 12").
   - Convert every date strictly to the ISO 8601 standard format: `YYYY-MM-DD`.
   - **Year Inference:** If the year is omitted in the row, infer it from the statement's cycle date.

2. **CURRENCY NORMALIZATION:**
   - Strip all currency symbols (`$`, `€`, etc.) and whitespace.
   - **Decimal Standardization:** Convert European formats (`1.234,56`) and US formats (`1,234.56`) strictly to standard Python floats (`1234.56`).

3. **TRANSACTION CLASSIFICATION:**
   - Use regex to determine if an amount is a charge (debit) or a deposit (credit).
   - **Indicators:** Charges may be indicated by a minus sign (`-12.50`), parentheses `(12.50)`, or specific column placement ("Withdrawals/Debits").

4. **OUTPUT:**
   - Return normalized strings and floats ready for schema mapping.

## Constraints
- Date conversion must be strictly ISO 8601.
- Currency symbols must be stripped before float conversion.
