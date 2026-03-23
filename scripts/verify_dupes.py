import csv
from datetime import datetime
import json

filepath = r"C:\Users\qqqq\Downloads\transactions_101-001-38641822-001 (1).csv"

open_trades = {}
overlap_found = False

with open(filepath, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ttype = row.get('TRANSACTION TYPE', '')
        pair = row.get('INSTRUMENT', '')
        details = row.get('DETAILS', '')
        
        if not pair:
            continue
            
        if ttype == 'ORDER_FILL' and details == 'MARKET_ORDER':
            if pair in open_trades:
                print(f"DUPLICATE DETECTED! {pair} opened at {open_trades[pair]['time']} and AGAIN at {row['TRANSACTION DATE']}")
                overlap_found = True
            else:
                open_trades[pair] = {'time': row['TRANSACTION DATE'], 'units': row['UNITS']}
                
        elif ttype == 'ORDER_FILL' and details in [
            'TRAILING_STOP_LOSS_ORDER', 'STOP_LOSS_ORDER', 'TAKE_PROFIT_ORDER', 
            'TRADE_CLOSE', 'POSITION_CLOSEOUT', 'CLIENT_ORDER', 'MARGIN_CLOSEOUT'
        ]:
            # Trade closed
            if pair in open_trades:
                del open_trades[pair]

if not overlap_found:
    print("No strict overlapping duplicate trades found. False positives from earlier are resolved.")
