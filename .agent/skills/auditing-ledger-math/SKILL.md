---
name: auditing-ledger-math
description: Validates mathematical consistency of financial ledgers. Use to verify start/end balances.
---
# Ledger Math Auditor
## Cuándo usar este skill
- Verificación final de integridad de datos.
## Instrucciones
Comprueba que Sum(charges) y Sum(deposits) coincidan con el cambio de balance.
```python
def audit(transactions: list, start_bal: float, end_bal: float):
    # Math validation
    return "VALID" # or "INVALID"
```
