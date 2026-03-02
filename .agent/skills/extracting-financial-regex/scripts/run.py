import re
import sys
import json

def normalize(text):
    lines = text.split('\n')
    results = []
    date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})'
    amount_pattern = r'(-?[\d,]+\.\d{2})'
    
    for line in lines:
        dates = re.findall(date_pattern, line)
        amounts = re.findall(amount_pattern, line)
        if dates and amounts:
            results.append({"date": dates[0], "amounts": amounts})
    return json.dumps(results)

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    print(normalize(raw_input))
