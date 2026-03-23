import csv
from collections import defaultdict
from datetime import datetime
import dateutil.parser

file_path = r"C:\Users\qqqq\Downloads\transactions_101-001-38641822-001 (1).csv"

orders = defaultdict(list)

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # We look for market orders created by the client
        if row['TRANSACTION TYPE'] == 'MARKET_ORDER' and row['DETAILS'] == 'CLIENT_ORDER':
            inst = row['INSTRUMENT']
            time_str = row['TRANSACTION DATE']
            try:
                # Example: 2025-03-04T12:00:00.000000000Z
                dt = dateutil.parser.parse(time_str)
                orders[inst].append({'time': dt, 'row': row})
            except Exception as e:
                print(f"Error parsing date {time_str}: {e}")

dupes_found = 0
for inst, inst_orders in orders.items():
    inst_orders.sort(key=lambda x: x['time'])
    for i in range(1, len(inst_orders)):
        prev = inst_orders[i-1]
        curr = inst_orders[i]
        diff = (curr['time'] - prev['time']).total_seconds()
        
        # If orders are placed within 60 minutes of each other
        if diff < 3600:
            if dupes_found == 0:
                print("Potential Duplicate Orders Found:")
            print(f"\n--- {inst} Duplicates ---")
            print(f"  Order 1: {prev['time']} | ID: {prev['row']['TRANSACTION ID']} | Units: {prev['row']['UNITS']}")
            print(f"  Order 2: {curr['time']} | ID: {curr['row']['TRANSACTION ID']} | Units: {curr['row']['UNITS']}")
            print(f"  Time Difference: {diff} seconds")
            dupes_found += 1

if dupes_found == 0:
    print("No duplicates found within 1 hour windows.")
