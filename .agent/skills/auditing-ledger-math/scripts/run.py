import json
import sys

def audit(data_json, start_bal, end_bal):
    transactions = json.loads(data_json)
    current_calc = start_bal
    for tx in transactions:
        current_calc += tx['deposit']
        current_calc -= tx['charge']
    
    if abs(current_calc - end_bal) < 0.01:
        return "VALID"
    else:
        return f"INVALID: Expected {end_bal}, got {current_calc}"

if __name__ == "__main__":
    data = sys.stdin.read()
    # Expecting start/end bal as env vars or args
    import os
    start = float(os.environ.get('START_BAL', 0))
    end = float(os.environ.get('END_BAL', 0))
    print(audit(data, start, end))
