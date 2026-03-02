---
name: json_schema_enforcer
version: 1.0.0
description: "Map the normalized data into a strict, immutable JSON structure. Prevent any conversational AI text in the output."
---

# JSON SCHEMA ENFORCER
**Objective:** Map the normalized data into a strict, immutable JSON structure. Prevent any conversational AI text in the output.

## Instructions

1. **JSON MAPPING:** Map the data row by row strictly into an array of JSON objects.
2. **SCHEMA SPECIFICATION:** The schema for EACH object MUST be exactly:
   ```json
   {
     "date": "YYYY-MM-DD",
     "description": "string",
     "charge": float or null,
     "deposit": float or null,
     "balance": float or null
   }
   ```
3. **MULTI-LINE HANDLING:** If a transaction description spans multiple lines in the raw text, concatenate them into a single string (e.g., "UBER *TRIP \n SAN FRANCISCO" becomes "UBER *TRIP SAN FRANCISCO").
4. **NULL VALUES:** If a field is missing, use `null`. Do not leave keys empty or use placeholder text.
5. **OUTPUT CONSTRAINT:** Output ONLY the raw JSON array. 
   - DO NOT include markdown formatting (like \` \` \` json).
   - DO NOT include introductions or explanations.

## Constraints
- Output must be valid JSON parseable by standard libraries.
- Absolute prohibition of non-JSON text in the final output.
