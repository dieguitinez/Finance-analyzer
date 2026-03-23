import csv

filepath = r"C:\Users\qqqq\Downloads\transactions_101-001-38641822-001.csv"

trades = []
longs = 0
shorts = 0
eur_usd_trades = []

with open(filepath, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print("Columns:", reader.fieldnames)
    for row in reader:
        ttype = row.get('TRANSACTION TYPE', '')
        pair = row.get('INSTRUMENT', '')
        details = row.get('DETAILS', '')
        pnl_str = row.get('PL', '0')
        units_str = row.get('UNITS', '0')
        time_str = row.get('TRANSACTION DATE', '')
        
        try:
            pnl = float(pnl_str) if pnl_str else 0.0
            units = float(units_str) if units_str else 0.0
        except ValueError:
            pnl = 0.0
            units = 0.0

        if ttype == 'ORDER_FILL' and details == 'MARKET_ORDER':
            # This is an open
            direction = "LONG" if units > 0 else "SHORT" if units < 0 else "UNKNOWN"
            if direction == "LONG": longs += 1
            if direction == "SHORT": shorts += 1
            
            trades.append({
                'time': time_str,
                'pair': pair,
                'direction': direction,
                'units': units,
                'pnl': pnl
            })
            if 'EUR_USD' in pair or 'USD_EUR' in pair:
                eur_usd_trades.append(trades[-1])
        elif ttype == 'ORDER_FILL' and details in ['TRAILING_STOP_LOSS_ORDER', 'STOP_LOSS_ORDER', 'TAKE_PROFIT_ORDER', 'TRADE_CLOSE', 'POSITION_CLOSEOUT', 'MARGIN_CLOSEOUT']:
            # This is a close, let's just log EUR_USD closes to match with PNL
            if 'EUR_USD' in pair or 'USD_EUR' in pair:
                eur_usd_trades.append({
                    'time': time_str,
                    'pair': pair,
                    'direction': 'CLOSE',
                    'units': units,
                    'pnl': pnl,
                    'reason': details
                })

print(f"Total Market Orders matching: {len(trades)}")
print(f"Longs: {longs}, Shorts: {shorts}")

print("\nRecent EUR_USD activity:")
for t in eur_usd_trades[-10:]:
    print(t)
