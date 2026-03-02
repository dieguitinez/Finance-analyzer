import json
import sys

def enforce(data):
    raw_list = json.loads(data)
    structured = []
    for item in raw_list:
        amounts = [float(a.replace(',', '')) for a in item['amounts']]
        # Assuming last column is balance, middle is charge/deposit
        charge = amounts[0] if amounts[0] < 0 else 0.0
        deposit = amounts[0] if amounts[0] > 0 else 0.0
        balance = amounts[-1]
        structured.append({
            "date": item['date'],
            "description": "Transaction Detail",
            "charge": abs(charge),
            "deposit": deposit,
            "balance": balance
        })
    return json.dumps(structured)

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    print(enforce(raw_input))
