import re
import sys
import json

def sanitize(data):
    # Redact account numbers (10-12 digits)
    data = re.sub(r'\b\d{10,12}\b', '[REDACTED_ACCOUNT]', data)
    # Redact common name-like patterns (Simplified for autonomous execution)
    data = re.sub(r'NAME:\s*[A-Z\s]+', 'NAME: [REDACTED_NAME]', data)
    return data

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    print(sanitize(raw_input))
