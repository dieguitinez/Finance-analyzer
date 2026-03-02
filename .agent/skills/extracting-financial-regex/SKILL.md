---
name: extracting-financial-regex
description: Normalizes financial data using regular expressions. Use for YYYY-MM-DD and float conversion.
---
# Regex Financial Extractor
## Cuándo usar este skill
- Normalización de fechas y montos.
## Instrucciones
Extrae fechas y números decimales.
```python
import re
def extract_fields(text: str):
    # Regex logic for dates and amounts
    return {"date": "2024-01-01", "amount": 100.0}
```
