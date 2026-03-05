import csv
from datetime import datetime
from collections import defaultdict

filepath = r"C:\Users\qqqq\Downloads\transactions_101-001-38641822-001 (1).csv"

trades = {}
completed_trades = []

with open(filepath, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ttype = row.get('TRANSACTION TYPE', '')
        pair = row.get('INSTRUMENT', '')
        details = row.get('DETAILS', '')
        pnl_str = row.get('PL', '0')
        time_str = row.get('TRANSACTION DATE', '')
        
        if not pair:
            continue
            
        try:
            pnl = float(pnl_str) if pnl_str else 0.0
        except ValueError:
            pnl = 0.0

        if ttype == 'ORDER_FILL' and details == 'MARKET_ORDER':
            # Open Trade
            if pair not in trades:
                trades[pair] = {'open_time': time_str, 'units': row.get('UNITS', 0)}
        elif ttype == 'ORDER_FILL' and details in ['TRAILING_STOP_LOSS_ORDER', 'STOP_LOSS_ORDER', 'TAKE_PROFIT_ORDER', 'TRADE_CLOSE', 'POSITION_CLOSEOUT', 'MARGIN_CLOSEOUT']:
            # Close Trade
            if pair in trades:
                open_time = trades[pair]['open_time']
                completed_trades.append({
                    'pair': pair,
                    'open_time': open_time,
                    'close_time': time_str,
                    'pnl': pnl,
                    'reason': details
                })
                del trades[pair]
        # Some PNL might be logged separately or as part of the fill
        # The PL column in Oanda usually populates on the closing ORDER_FILL

# Analysis
total_trades = len(completed_trades)
winning_trades = [t for t in completed_trades if t['pnl'] > 0]
losing_trades = [t for t in completed_trades if t['pnl'] <= 0]

print(f"--- OANDA TRADING ANALYSIS ---")
print(f"Total Trades Analyzed: {total_trades}")

if total_trades > 0:
    win_rate = len(winning_trades) / total_trades * 100
    print(f"Win Rate: {win_rate:.2f}% ({len(winning_trades)} W / {len(losing_trades)} L)")
    
    total_profit = sum(t['pnl'] for t in winning_trades)
    total_loss = sum(t['pnl'] for t in losing_trades)
    net_pnl = total_profit + total_loss
    
    print(f"Gross Profit: ${total_profit:.2f}")
    print(f"Gross Loss: ${total_loss:.2f}")
    print(f"Net PnL: ${net_pnl:.2f}")
    
    avg_win = total_profit / len(winning_trades) if winning_trades else 0
    avg_loss = total_loss / len(losing_trades) if losing_trades else 0
    
    print(f"Average Win: ${avg_win:.2f}")
    print(f"Average Loss: ${avg_loss:.2f}")
    if avg_loss != 0:
        print(f"Reward/Risk Ratio: {abs(avg_win / avg_loss):.2f}")

    pair_stats = defaultdict(lambda: {'ws': 0, 'ls': 0, 'pnl': 0.0})
    reason_stats = defaultdict(int)

    for t in completed_trades:
        p = t['pair']
        pair_stats[p]['pnl'] += t['pnl']
        if t['pnl'] > 0:
            pair_stats[p]['ws'] += 1
        else:
            pair_stats[p]['ls'] += 1
        reason_stats[t['reason']] += 1

    print("\n--- PERFORMANCE BY PAIR ---")
    sorted_pairs = sorted(pair_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
    for pair, stats in sorted_pairs:
        total = stats['ws'] + stats['ls']
        wr = stats['ws'] / total * 100 if total > 0 else 0
        print(f"{pair}: Net ${stats['pnl']:.2f} | WR: {wr:.1f}% ({stats['ws']}W/{stats['ls']}L)")

    print("\n--- CLOSURE REASONS ---")
    for reason, count in sorted(reason_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"{reason}: {count} ({count/total_trades*100:.1f}%)")
else:
    print("No completed trades found to analyze.")
