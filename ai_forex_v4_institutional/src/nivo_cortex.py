import os
import numpy as np
import pandas as pd
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    class GaussianHMM:
        def __init__(self, *args, **kwargs): pass
        def fit(self, *args, **kwargs): pass
        def predict(self, *args, **kwargs): return [0]
    HMM_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    torch.set_num_threads(1)
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Mock nn.Module for class inheritance safety
    class nn:
        class Module: pass

import requests
import warnings
import gc

# Ensure flags are globally accessible for Lite Mode detection
__all__ = ['NivoCortex', 'MarketRegimeDetector', 'TORCH_AVAILABLE', 'HMM_AVAILABLE']

# Suppress known benign hmmlearn init warnings (parameter overwrite is expected behavior)
warnings.filterwarnings("ignore", message=".*init_params.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*transmat_.*zero sum.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*startprob_.*", category=UserWarning)


# ============================================================================
# 1. MarketRegimeDetector (HMM-based)
# ============================================================================
class MarketRegimeDetector:
    """
    Hidden Markov Model for regime classification.
    3 hidden states: Low Volatility, High Volatility, Crash Mode.
    Uses float32 arrays for memory efficiency.
    """
    REGIME_MAP = {
        0: "LOW_VOLATILITY",
        1: "HIGH_VOLATILITY",
        2: "CRASH_MODE"
    }
    REGIME_DESC = {
        0: "Calm / Low Volatility",
        1: "Elevated Volatility",
        2: "Crash / Extreme Regime"
    }

    # Minimum number of observations required to train HMM reliably
    MIN_TRAIN_SAMPLES = 150

    def __init__(self):
        # Use 'diag' covariance for stability with small/sparse forex datasets.
        # 'full' requires many more observations per state to avoid singular matrices.
        # n_iter=200 + tol=1e-3 gives EM enough iterations to converge on sparse data.
        # random_state ensures reproducible initialization.
        self.model = GaussianHMM(
            n_components=3,
            covariance_type="diag",
            n_iter=200,
            tol=1e-3,
            random_state=42,
        )
        self.is_trained = False

    def _prepare_data(self, returns: np.ndarray) -> np.ndarray | None:
        """
        Cleans return series and returns a float64 column vector for HMM.
        Returns None if data is insufficient or degenerate.
        NOTE: float64 is mandatory here — float32 causes NaN during EM iterations
        in hmmlearn because intermediate covariance calculations lose precision.
        """
        rt_flat = returns.flatten() if hasattr(returns, "flatten") else np.array(returns)
        # Replace ±inf before converting to float64 to avoid overflow
        clean = pd.Series(rt_flat.astype(np.float64)).replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < self.MIN_TRAIN_SAMPLES:
            return None
        data = clean.values.reshape(-1, 1)
        # Check for degenerate data: zero or near-zero variance kills HMM covariance matrices
        if np.std(data) < 1e-10:
            return None
        # Final safety check: reject if any NaN/Inf slipped through
        if not np.all(np.isfinite(data)):
            return None
        return data

    def train(self, returns: np.ndarray, pair: str = "GLOBAL"):
        """Train HMM on cleaned return series and persist result."""
        data = self._prepare_data(returns)
        if data is None:
            self.is_trained = False
            return
        try:
            self.model.fit(data)
            self.is_trained = True
            self.save_model(pair)
        except Exception as e:
            self.is_trained = False
            print(f"[HMM] Training failed: {e}")

    def save_model(self, pair: str):
        """Persists HMM weights to disk."""
        import joblib
        try:
            path = os.path.join(os.path.dirname(__file__), "data", f"hmm_{pair.replace('/','_')}.pkl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            joblib.dump(self.model, path)
        except Exception as e:
            print(f"[HMM] Save failed: {e}")

    def load_model(self, pair: str) -> bool:
        """Loads persisted HMM weights."""
        import joblib
        try:
            path = os.path.join(os.path.dirname(__file__), "data", f"hmm_{pair.replace('/','_')}.pkl")
            if os.path.exists(path):
                self.model = joblib.load(path)
                self.is_trained = True
                return True
        except Exception as e:
            print(f"[HMM] Load failed: {e}")
        return False

    def detect_regime(self, df: pd.DataFrame):
        """
        Returns (regime_id: int, regime_description: str).
        This is the method app.py calls via cortex.hmm.detect_regime(data).
        """
        if not self.is_trained:
            returns = df['Close'].pct_change().dropna().values.flatten()
            if len(returns) >= self.MIN_TRAIN_SAMPLES:
                self.train(returns[-500:])

        if not self.is_trained:
            return -1, "Unknown (Insufficient Data)"

        returns = df['Close'].pct_change().dropna().values
        data = self._prepare_data(returns)
        if data is None:
            return -1, "Unknown (Degenerate Data)"
        try:
            hidden_states = np.array(self.model.predict(data))  # ensure numpy array for indexing
            current_state = int(hidden_states[-1])
        except Exception as e:
            return -1, f"Unknown (Model Error: {str(e)[:20]})"

        # Sort by mean to assign semantic labels
        try:
            means = self.model.means_.flatten()
        except AttributeError:
             return -1, "Unknown (Training Incomplete)"
             
        sorted_indices = np.argsort(means)

        # Map raw state to semantic regime
        if current_state == sorted_indices[0]:
            regime_id = 2  # Lowest mean = crash
        elif current_state == sorted_indices[2]:
            regime_id = 0  # Highest mean = low vol (bullish)
        else:
            regime_id = 1  # Middle = high vol

        return regime_id, self.REGIME_DESC.get(regime_id, "Unknown")

    def get_regime_string(self, df: pd.DataFrame) -> str:
        """Returns string regime label for the Supervisor Handshake."""
        regime_id, _ = self.detect_regime(df)
        return self.REGIME_MAP.get(regime_id, "UNKNOWN")


# ============================================================================
# 2. CPUOptimizedLSTM (PyTorch Neural Net)
# ============================================================================
class CPUOptimizedLSTM(nn.Module):
    """
    LSTM architecture — must exactly match scripts/train_lstm.py.
    input_size=5  (open_r, high_r, low_r, close_r, vol_n)
    hidden_size=64, num_layers=2, dropout=0.2, fc + sigmoid output.
    """
    def __init__(self, input_size=7, hidden_size=64, num_layers=2, output_size=1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc   = nn.Linear(hidden_size, output_size)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.sigmoid(self.fc(out[:, -1, :]))



class NivoLSTM:
    """
    LSTM predictor wrapper.
    Provides predict_next_move(df) -> (status_str, probability_float)
    which is what app.py calls via cortex.lstm.predict_next_move(data).
    Auto-loads trained weights from scripts/data/lstm_{pair}.pth if available.
    """
    def __init__(self, pair: str = ""):
        self.model = CPUOptimizedLSTM(input_size=7)
        self.is_trained = False
        self.pair = pair

        # Try to load pre-trained weights for this pair
        if pair:
            _script_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "scripts", "data"
            )
            # Normalize pair name: 'EUR/USD' → 'EUR_USD' to match file naming convention
            pair_safe = pair.replace("/", "_")
            weights_path = os.path.join(_script_dir, f"lstm_{pair_safe}.pth")
            if os.path.exists(weights_path):
                try:
                    state_dict = torch.load(weights_path, map_location="cpu")
                    self.model.load_state_dict(state_dict)
                    self.is_trained = True
                    print(f"[NivoLSTM] [OK] Loaded trained weights for {pair}")
                except Exception as e:
                    print(f"[NivoLSTM] [WARN] Could not load weights for {pair}: {e} — using random weights")
            else:
                print(f"[NivoLSTM] [INFO] No trained weights found for {pair} — using random weights")
                print(f"             Run: python3 scripts/train_lstm.py to train")

        self.model.eval()


    def predict_next_move(self, df: pd.DataFrame):
        """
        Returns (status_string, bull_probability_float 0-100).
        Prepares same 5-feature input as train_lstm.py:
          [open_r, high_r, low_r, close_r, vol_n] over last 60 candles.
        """
        try:
            SEQ_LEN = 120 # Upgraded from 60
            if len(df) < SEQ_LEN + 1:
                return "Insufficient Data", 50.0

            # Ensure V4 features exist (calculated in TradeBrain)
            required = ["VWAP_Dist", "ATR", "EMA_20_Slope", "EMA_200"]
            for col in required:
                if col not in df.columns:
                    return f"Missing Feature: {col}", 50.0

            df = df.copy()
            # 1. Close Retorno Log (more stable than pct_change)
            df["log_ret"] = np.log(df["Close"] / df["Close"].shift(1))
            
            # 2. Normalized Price (Distance from SMA 20)
            df["price_norm"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).std()
            
            # 3. Volume Delta (Normalized)
            df["vol_delta"] = (df["Volume"] - df["Volume"].rolling(20).mean()) / (df["Volume"].rolling(20).std() + 1e-8)

            # 4. EMA 200 Distance
            df["ema200_dist"] = (df["Close"] - df["EMA_200"]) / df["EMA_200"]

            df = df.dropna()

            if len(df) < SEQ_LEN:
                return "Insufficient Data", 50.0

            # Final Feature List (7):
            # [price_norm, log_ret, VWAP_Dist, vol_delta, ATR, ema200_dist, EMA_20_Slope]
            features_list = ["price_norm", "log_ret", "VWAP_Dist", "vol_delta", "ATR", "ema200_dist", "EMA_20_Slope"]
            features = df[features_list].values[-SEQ_LEN:].astype(np.float32)

            with torch.no_grad():
                tensor = torch.from_numpy(features).unsqueeze(0)  # shape: (1, 120, 7)
                prediction = self.model(tensor).item()

            bull_prob = round(float(prediction) * 100, 1)

            # Guard against NaN or invalid outputs (overflow in rare cases)
            import math
            if math.isnan(bull_prob) or not (0.0 <= bull_prob <= 100.0):
                print(f"[NivoLSTM] ⚠️ NaN/invalid output for {self.pair}. Fallback to 50.0")
                bull_prob = 50.0

            if bull_prob > 55:
                status = "Bullish Momentum"
            elif bull_prob < 45:
                status = "Bearish Pressure"
            else:
                status = "Neutral / Indecisive"

            return status, bull_prob
        except Exception as e:
            return f"LSTM Error: {str(e)}", 50.0



# ============================================================================
# 3. OrderBookAnalyzer (OANDA DOM)
# ============================================================================
class OrderBookAnalyzer:
    """
    Analyzes OANDA v20 order book for microstructure bias.
    Returns dict with 'outlook' key.
    """
    def __init__(self, oanda_token: str = "", oanda_id: str = ""):
        self.oanda_token = oanda_token
        self.oanda_id = oanda_id

    def analyze(self, instrument: str) -> dict:
        """
        Fetches order book from OANDA and computes bid/ask imbalance.
        Returns dict with 'outlook' or 'error' key.
        """
        if not self.oanda_token:
            return {"outlook": "Disabled (No API Key)", "imbalance": 0.0}

        try:
            # Determine correct host based on account ID
            host = "api-fxtrade.oanda.com" if "live" in self.oanda_id.lower() else "api-fxpractice.oanda.com"
            url = f"https://{host}/v3/instruments/{instrument}/orderBook"
            headers = {"Authorization": f"Bearer {self.oanda_token}"}
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code != 200:
                err_msg = response.json().get('errorMessage', f'API {response.status_code}')
                return {"error": err_msg, "outlook": "Error"}

            data = response.json()
            buckets = data.get("orderBook", {}).get("buckets", [])

            if not buckets:
                return {"outlook": "No Data", "imbalance": 0.0}

            total_long = sum(float(b.get("longCountPercent", 0)) for b in buckets)
            total_short = sum(float(b.get("shortCountPercent", 0)) for b in buckets)

            denominator = total_long + total_short
            if denominator == 0:
                return {"outlook": "Neutral", "imbalance": 0.0}

            imbalance = (total_long - total_short) / denominator

            if imbalance > 0.1:
                outlook = "Bullish Bias (Long Heavy)"
            elif imbalance < -0.1:
                outlook = "Bearish Bias (Short Heavy)"
            else:
                outlook = "Balanced"

            return {"outlook": outlook, "imbalance": round(imbalance, 4)}

        except Exception as e:
            return {"error": str(e), "outlook": "Error"}


# ============================================================================
# 4. NivoCortex (Orchestrator)
# ============================================================================
class NivoCortex:
    """
    Nivo Cortex: The AI Intelligence Layer.
    Orchestrates HMM regime detection, LSTM prediction, and DOM analysis.

    API Contract (what app.py expects):
        cortex = NivoCortex(data, oanda_token=token)
        regime = cortex.detect_market_regime()        -> str
        cortex.hmm.detect_regime(data)                -> (int, str)
        prediction = cortex.predict_next_move()       -> str
        cortex.lstm.predict_next_move(data)           -> (str, float)
        cortex.analyze_order_book(symbol)             -> dict
    """
    def __init__(self, data: pd.DataFrame = None, oanda_token: str = "", oanda_id: str = "", pair: str = ""):
        self.data = data
        self.oanda_token = oanda_token
        self.oanda_id = oanda_id
        self.pair = pair

        # Sub-modules accessible as attributes
        self.hmm = MarketRegimeDetector()
        self.lstm = NivoLSTM(pair=pair)  # Loads trained .pth if available
        self.order_book = OrderBookAnalyzer(oanda_token, oanda_id)

        # V6 Persistent Memory: Try to load existing HMM weights first
        self.hmm.load_model(pair or "GLOBAL")

        # Auto-train HMM if data provided and NOT already loaded from disk
        if data is not None and len(data) >= 150 and not self.hmm.is_trained:
            returns = data['Close'].pct_change().dropna().values
            self.hmm.train(returns[-500:], pair=pair or "GLOBAL")
        
        # Mandatory RAM Guard (V6)
        gc.collect()

    def detect_market_regime(self) -> str:
        """Returns regime string: LOW_VOLATILITY, HIGH_VOLATILITY, CRASH_MODE, or UNKNOWN."""
        if self.data is None:
            return "UNKNOWN"
        return self.hmm.get_regime_string(self.data)

    def predict_next_move(self) -> str:
        """Returns 'UP', 'DOWN', or 'UNKNOWN'."""
        if self.data is None:
            return "UNKNOWN"
        try:
            status, prob = self.lstm.predict_next_move(self.data)
            if prob > 55:
                return "UP"
            elif prob < 45:
                return "DOWN"
            else:
                return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def analyze_order_book(self, instrument: str) -> dict:
        """Proxies to OrderBookAnalyzer."""
        return self.order_book.analyze(instrument)

    def evaluate_veto(self, df: pd.DataFrame = None):
        """
        V6 AI Filter: Ensures AI probability aligns with technical trend.
        Acts as the final gatekeeper.
        """
        target = df if df is not None else self.data
        if target is None or len(target) < 150:
            return True, "SYSTEM VETO: Insufficient historical data for AI context."

        # 1. HMM Regime Check
        regime_id, regime_desc = self.hmm.detect_regime(target)
        regime_str = self.hmm.get_regime_string(target)

        # 2. LSTM Vector
        status, prob = self.lstm.predict_next_move(target)
        
        # 3. Trend Alignment (Sync with NivoTradeBrain)
        try:
            ema_50 = target['EMA_50'].iloc[-1]
            ema_200 = target['EMA_200'].iloc[-1]
            is_bullish_trend = ema_50 > ema_200
        except KeyError:
            # V6 Fallback: If indicators missing, we don't veto on trend yet
            is_bullish_trend = True 

        veto = False
        reason = f"Regime: {regime_str} | AI Confidence: {prob}%"

        # V6 RULES: 
        # A. If Bullish Trend but AI is heavily Bearish (< 30%), Veto (Divergence Risk).
        if is_bullish_trend and prob < 30.0:
            veto = True
            reason = f"SYSTEM VETO: AI Contradiction. Trend is BULLISH but AI Vector is HEAVILY BEARISH ({prob}%)."
        
        # B. If Bearish Trend but AI is heavily Bullish (> 70%), Veto.
        elif not is_bullish_trend and prob > 70.0:
            veto = True
            reason = f"SYSTEM VETO: AI Contradiction. Trend is BEARISH but AI Vector is HEAVILY BULLISH ({prob}%)."

        # C. Crash Mode Handling (V6 Balanced)
        if regime_str == "CRASH_MODE":
            if prob > 40 and prob < 60:
                veto = True
                reason = "SYSTEM VETO: Extreme Volatility (Crash) & Low AI Conviction. Neutralizing risk."
            else:
                 # If AI is very strong in one direction during crash, we allow it (Trend Following or Catching Knife)
                 reason += " | EXTREME VOLATILITY: Proceeding due to High AI Conviction."

        return veto, reason

    def get_auto_execution_signal(self, df: pd.DataFrame, brain_analysis: dict):
        """
        Final decision engine for the Auto-Trader.
        Combines V6 Technical Brain + V6 AI Cortex.
        """
        signal = brain_analysis.get("signal", "WAIT")
        if signal == "WAIT":
            return "STANDBY", "Brain Signal: WAIT"

        veto, reason = self.evaluate_veto(df)
        
        if veto:
            return "STANDBY", reason
            
        if "BUY" in signal:
            return "EXECUTE_LONG", f"Cortex Approved | {reason}"
        elif "SELL" in signal:
            return "EXECUTE_SHORT", f"Cortex Approved | {reason}"
            
        return "STANDBY", "Decision Logic End"
