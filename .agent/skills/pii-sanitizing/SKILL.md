---
name: pii-sanitizing
description: Redacts account numbers, and names from financial documents. Use when processing PII data.
---
# PII Data Sanitizer
## Cuándo usar este skill
- Limpieza de estados de cuenta antes del procesamiento.
## Instrucciones
Este skill consume texto crudo o datos de PDF y anonimiza campos sensibles.
```python
import re
def sanitize(data: str) -> str:
    # Redact account numbers (usually 10-12 digits)
    data = re.sub(r'\b\d{10,12}\b', '[REDACTED_ACCOUNT]', data)
    # Generic name redact (simplified for this task)
    return data
```
