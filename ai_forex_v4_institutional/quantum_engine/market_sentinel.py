import sys
import os
import time
import requests
import json
import logging
import logging.handlers
import subprocess

# Ensure the project root is on the path so 'src' is importable
# This works both on Linux server and local Windows runs.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.notifications import NotificationManager
from src.utils import is_market_open

# Nivo FX Sentinel Logging with Rotation (7 days)
log_dir = os.path.join(_project_root, "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "nivo_sentinel.log")
handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=7)
formatter = logging.Formatter('%(asctime)s | NIVO SENTINEL: [%(levelname)s] | %(message)s')
handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler, logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Telegram shortcut (safe: silently skips if not configured) ---
def _notify(event_type, detail):
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        NotificationManager.telegram_alert(event_type, detail, token, chat_id)

# Lightweight mathematical proxies (No Pandas!)
def extract_highs_lows(json_data):
    """Parses OANDA style JSON data manually to extract High and Low prices."""
    highs, lows = [], []
    try:
        # Assuming typical OANDA or standard API output format
        # Adjust parsing logic if the actual API payload differs
        if "candles" in json_data:
            for c in json_data["candles"][-10:]:
                if c["complete"]:
                    highs.append(float(c["mid"]["h"]))
                    lows.append(float(c["mid"]["l"]))
        elif "data" in json_data:
            # Fallback for generic APIs (like Coingecko or similar standard)
            for d in json_data["data"][-10:]:
                highs.append(float(d.get("high", 0)))
                lows.append(float(d.get("low", 0)))
                
        return highs, lows
    except Exception as e:
        logger.error(f"Error parsing JSON: {e}")
        return [], []

def check_asian_range_breakout(highs, lows, current_price):
    """
    Checks if current price is breaking the range established in recent history (Proxy for Asian Range).
    """
    if len(highs) < 10: return False
    
    # We compare current price to the extremes of the previous candles
    asian_high = max(highs[:-1])
    asian_low = min(lows[:-1])
    
    if current_price > asian_high or current_price < asian_low:
        return True
    return False

def get_scoring_trigger(pair="EUR_USD", tf="H1"):
    """
    Nivo V4 Scoring Sentinel. Sums points across ATR, Asian Range, and DOM.
    """
    logger.info(f"V4 Scoring Scan for {pair} @ {tf}")
    
    oanda_token = os.getenv("OANDA_ACCESS_TOKEN", "")
    oanda_account = os.getenv("OANDA_ACCOUNT_ID", "")
    base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    
    if not oanda_token:
        # Probabilistic simulation for testing if no API key
        import random
        sim_score = random.choice([0, 1, 2, 3])
        return sim_score >= 2, {"score": sim_score, "reasons": ["SIMULATED_V4"]}

    trigger_score = 0
    reasons = []
    
    try:
        url = f"{base_url}/v3/instruments/{pair}/candles"
        params = {"count": 20, "granularity": tf, "price": "M"}
        headers = {"Authorization": f"Bearer {oanda_token}"}
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        highs, lows = extract_highs_lows(data)
        
        if not highs: return False, {}

        current_price = float(data["candles"][-1]["mid"]["c"])
        
        # 1. ATR EXPANSION
        ranges = [h - l for h, l in zip(highs, lows)]
        atr_avg = sum(ranges[:-1]) / len(ranges[:-1])
        recent_range = highs[-1] - lows[-1]
        
        if recent_range > (atr_avg * 1.5):
            trigger_score += 1
            reasons.append("ATR Expansion")

        # 2. ASIAN RANGE BREAKOUT
        if check_asian_range_breakout(highs, lows, current_price):
            trigger_score += 1
            reasons.append("Asian Range/History Breakout")

        # 3. DOM IMBALANCE
        from src.nivo_cortex import OrderBookAnalyzer
        analyzer = OrderBookAnalyzer(oanda_token, oanda_account)
        dom_data = analyzer.analyze(pair)
        imbalance = abs(dom_data.get("imbalance", 0.0))
        
        if imbalance > 0.6:
            trigger_score += 1
            reasons.append(f"DOM Imbalance ({imbalance*100:.1f}%)")

        is_triggered = trigger_score >= 2
        return is_triggered, {"score": trigger_score, "reasons": reasons}

    except Exception as e:
        logger.error(f"Scoring Error for {pair}: {e}")
        return False, {}

def check_volatility_expansion(pair="EUR_USD", tf="H1", threshold_bps=75.0):
    """
    Minimalist Volatility Check.
    If the recent price swing exceeds the threshold in basis points, trigger an event.
    """
    logger.info(f"Checking for Volatility Expansion on {pair} @ {tf}")
    
    # In a true deployment, load from os.getenv. Defaulting to free API for the Sentinel to save overhead
    # In production, replace this URL with the secured DEMO_BASE_URL + instrument endpoint
    # Here, we use a public/free endpoint structure as a structural example if OANDA isn't provided
    oanda_token = os.getenv("OANDA_ACCESS_TOKEN", "")
    oanda_account = os.getenv("OANDA_ACCOUNT_ID", "")
    base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    
    if not oanda_token:
        # If no auth is provided, we simulate a volume spike probabilistically for demonstration
        # so the VM executor actually triggers during testing.
        import random
        simulated_bps = random.uniform(5.0, 25.0)
        logger.info(f"Running without API keys. Simulating Volatility: {simulated_bps:.1f} bps.")
        return simulated_bps > threshold_bps

    # Real API fetch logic (Lightweight Requests, no DataFrame overhead)
    url = f"{base_url}/v3/instruments/{pair}/candles"
    params = {"count": 10, "granularity": tf, "price": "M"}
    headers = {"Authorization": f"Bearer {oanda_token}"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        highs, lows = extract_highs_lows(data)
        
        if not highs or not lows:
            logger.warning("Could not extract pricing arrays.")
            return False
            
        # Pure math array operations (Vanilla Python / minimal memory)
        max_high = max(highs)
        min_low = min(lows)
        
        # Calculate expansion in basis points (1 bps = 0.0001)
        # Using a fixed denominator (e.g. 1.1000 for EURUSD proxy) or simply the min_low
        expansion_pct = (max_high - min_low) / min_low
        expansion_bps = expansion_pct * 10000 
        
        logger.info(f"Current Swing Expansion: {expansion_bps:.2f} bps. Threshold: {threshold_bps} bps.")
        return expansion_bps >= threshold_bps
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error establishing trigger condition: {e}")
        return False

def get_active_positions():
    """Fetches all instruments that currently have an open position in OANDA."""
    oanda_token = os.getenv("OANDA_ACCESS_TOKEN", "")
    oanda_account = os.getenv("OANDA_ACCOUNT_ID", "")
    base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    
    if not oanda_token or not oanda_account:
        return []
        
    url = f"{base_url}/v3/accounts/{oanda_account}/openPositions"
    headers = {"Authorization": f"Bearer {oanda_token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            positions = data.get("positions", [])
            # Return list of instruments like ['USD_CHF', 'USD_JPY']
            return [p["instrument"] for p in positions]
    except Exception as e:
        logger.error(f"Error checking active positions for Sentinel: {e}")
    return []

def awake_vm_executor(pair: str):
    """
    Triggers the heavy Python process (vm_executor.py) via subprocess isolation.
    """
    logger.warning(f"EVENTO DETECTADO: Despertando Motor Cuantico para {pair}...")
    # Sin alerta aqui - el vm_executor enviara la senal con los datos de trading
    
    try:
        # Determine paths dynamically
        script_dir = os.path.dirname(os.path.abspath(__file__))
        executor_path = os.path.join(script_dir, "vm_executor.py")
        
        if not os.path.exists(executor_path):
            logger.error(f"CRITICAL: Executor script not found at {executor_path}")
            sys.exit(1)
            
        # Spawn Subprocess
        # Using sys.executable ensures the same Python binary is used
        # We also pass the current working directory to PYTHONPATH so local modules like quantum_engine can be found
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
        env["TRADING_PAIR"] = pair
        
        start_time = time.time()
        process = subprocess.Popen(
            [sys.executable, executor_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        logger.info(f"Subprocess spawned with PID: {process.pid}. Waiting for execution...")
        
        # Blocking wait - The Sentinel pauses here, holding mere megabytes of RAM
        stdout, stderr = process.communicate()
        exit_code = process.returncode
        exec_time = time.time() - start_time
        
        # Log the exact output from the heavy engine
        logger.info(f"--- HEAVY ENGINE OUTPUT (Code {exit_code}, {exec_time:.2f}s) ---")
        if stdout:
            for line in stdout.splitlines():
                if line.strip(): logger.info(f"| {line}")
        if stderr:
            for line in stderr.splitlines():
                if line.strip(): logger.error(f"| {line}")
        logger.info("-----------------------------------------------------")
        
        if exit_code == 0:
            logger.info("Quantum computation and routing completed seamlessly.")
        else:
            logger.error(f"Quantum engine exited with error code {exit_code}.")
            
    except Exception as e:
        logger.error(f"Failed to spawn subprocess: {e}")

def run_sentinel():
    """Main execution entry point for multi-pair scanning."""
    if not is_market_open():
        logger.info("Mercado Cerrado (Fin de Semana). Sentinel en modo standby.")
        sys.exit(0)
        
    logger.info("Ciclo Sentinel Iniciado.")
    
    # 1. Get Watchlist
    # 0. Check for Panic Lock (Kill Switch)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    panic_lock_path = os.path.join(project_root, ".panic_lock")
    if os.path.exists(panic_lock_path):
        logger.warning("🚨 [KILL SWITCH] .panic_lock detected. Autonomous trading is HALTED.")
        sys.exit(0)

    # 1. Get Watchlist
    watchlist_env = os.getenv("WATCHLIST", os.getenv("TRADING_PAIR", "EUR_USD"))
    watchlist = [p.strip() for p in watchlist_env.split(',') if p.strip()]

    logger.info(f"Escaneando Watchlist: {watchlist}")
    
    triggered_pairs = []
    
    # 2. Evaluate Trigger Conditions for all pairs
    for pair in watchlist:
        is_triggered, details = get_scoring_trigger(pair)
        if is_triggered:
            logger.info(f"[OK] V4 TRIGGER for {pair}: Score {details['score']} - {details['reasons']}")
            triggered_pairs.append(pair)
        else:
            logger.info(f"Market Calm for {pair}. Score {details.get('score', 0)}")
    # --- NEW: Automated Tracking of Open Positions ---
    # We ensure that if there's a trade open, it always gets a report regardless of volatility
    active_positions = get_active_positions()
    for pos_pair in active_positions:
        if pos_pair not in triggered_pairs:
            logger.info(f"📋 Seguimiento Automático: Posición abierta detectada para {pos_pair}. Activando reporte.")
            triggered_pairs.append(pos_pair)
            
    # 3. Process Branching (Optimized: Single Process for all pairs)
    if triggered_pairs:
        # Join pairs with commas to pass to the executor
        pairs_str = ",".join(triggered_pairs)
        awake_vm_executor(pair=pairs_str)
    else:
        logger.info("Mercado tranquilo. Volatilidad bajo el umbral en todos los pares. Liberando RAM.")
        
    # 4. Explicit teardown
    sys.exit(0)

if __name__ == "__main__":
    run_sentinel()
