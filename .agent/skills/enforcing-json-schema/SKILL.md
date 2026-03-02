---
name: enforcing-json-schema
description: Maps and validates data against a specific JSON schema. Use for financial transaction arrays.
---
# JSON Schema Enforcer
## Cuándo usar este skill
- Estructuración de datos financieros en JSON.
## Instrucciones
Valida que el array de transacciones cumpla el esquema requerido.
```python
def enforce_schema(data_list: list):
    # Map and validate
    return [{"date": "...", "description": "...", "charge": 0.0, "deposit": 0.0, "balance": 0.0}]
```
