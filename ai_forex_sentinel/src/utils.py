import datetime
import pytz

def is_market_open():
    """
    Checks if the Forex market is currently open.
    Forex market hours: Sunday 5 PM ET to Friday 5 PM ET.
    """
    # Use Eastern Time for consistent weekend detection
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.datetime.now(eastern)
    
    # Weekday: 0=Monday, ..., 5=Saturday, 6=Sunday
    weekday = now_et.weekday()
    hour = now_et.hour
    
    # Friday after 5 PM
    if weekday == 4 and hour >= 17:
        return False
    # Saturday
    if weekday == 5:
        return False
    # Sunday before 5 PM
    if weekday == 6 and hour < 17:
        return False
        
    return True

if __name__ == "__main__":
    print(f"Market open: {is_market_open()}")
