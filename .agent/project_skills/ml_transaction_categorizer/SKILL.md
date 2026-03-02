---
name: ml_transaction_categorizer
version: 1.0.0
description: "Autonomously analyze normalized transaction descriptions and assign them to standardized personal finance categories."
---

# ML TRANSACTION CATEGORIZER
**Objective:** Autonomously analyze normalized transaction descriptions and assign them to standardized personal finance categories.

## Instructions
1. **Input:** Receive the mathematically validated JSON array of transactions.
2. **NLP Analysis:** For each transaction object, analyze the `description` string to identify the merchant type or intent.
3. **Category Mapping:** Map each transaction strictly to one of the following:
   - `Housing`
   - `Transportation`
   - `Food & Dining`
   - `Utilities`
   - `Insurance`
   - `Healthcare`
   - `Savings/Investments`
   - `Personal Spending`
   - `Income`
   - `Miscellaneous`
4. **Contextual Rules:**
   - **Income:** If `deposit > 0` and description contains "Payroll", "Salary", or "Zelle".
   - **Transportation:** If description contains "UBER", "LYFT", or "CHEVRON".
   - **Miscellaneous:** If the description is vague or has no clear merchant.
5. **Data Mutation:** Inject `"category": "Matched_Category"` into every transaction object.
6. **Output:** Return the updated JSON array.

## Master Categories
`["Housing", "Transportation", "Food & Dining", "Utilities", "Insurance", "Healthcare", "Savings/Investments", "Personal Spending", "Income", "Miscellaneous"]`
