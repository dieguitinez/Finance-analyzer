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

    def train(self, returns: np.ndarray):
        """Train HMM on cleaned return series."""
        data = self._prepare_data(returns)
        if data is None:
            self.is_trained = False
            return
        try:
            self.model.fit(data)
            self.is_trained = True
        except Exception as e:
            # Only log truly unexpected errors — convergence warnings are suppressed globally
            self.is_trained = False
            print(f"[HMM] Training failed: {e}")

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
            hidden_states = self.model.predict(data)  # data is float64
            current_state = int(hidden_states[-1])
        except Exception as e:
            return -1, f"Unknown (Model Error: {str(e)[:20]})"

        # Sort by mean to assign semantic labels
        means = self.model.means_.flatten()
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
    def __init__(self, input_size=5, hidden_size=64, num_layers=2, output_size=1):
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
        self.model = CPUOptimizedLSTM()
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
                    print(f"[NivoLSTM] ✅ Loaded trained weights for {pair}")
                except Exception as e:
                    print(f"[NivoLSTM] ⚠️ Could not load weights for {pair}: {e} — using random weights")
            else:
                print(f"[NivoLSTM] ℹ️ No trained weights found for {pair} — using random weights")
                print(f"             Run: python3 scripts/train_lstm.py to train")

        self.model.eval()


    def predict_next_move(self, df: pd.DataFrame):
        """
        Returns (status_string, bull_probability_float 0-100).
        Prepares same 5-feature input as train_lstm.py:
          [open_r, high_r, low_r, close_r, vol_n] over last 60 candles.
        """
        try:
            SEQ_LEN = 60
            if len(df) < SEQ_LEN + 1:
                return "Insufficient Data", 50.0

            df = df.copy()
            df["open_r"]  = df["Open"].pct_change()
            df["high_r"]  = df["High"].pct_change()
            df["low_r"]   = df["Low"].pct_change()
            df["close_r"] = df["Close"].pct_change()
            df["vol_n"]   = (df["Volume"] - df["Volume"].mean()) / (df["Volume"].std() + 1e-8)
            df = df.dropna()

            if len(df) < SEQ_LEN:
                return "Insufficient Data", 50.0

            features = df[["open_r", "high_r", "low_r", "close_r", "vol_n"]].values[-SEQ_LEN:].astype(np.float32)

            with torch.no_grad():
                tensor = torch.from_numpy(features).unsqueeze(0)  # shape: (1, 60, 5)
                prediction = self.model(tensor).item()             # sigmoid output: 0-1

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
    def __init__(self, data: pd.DataFrame = None, oanda_token: str = "", oanda_id: str = ""):
        self.system_prompt = """
        You are Kai FX, the Neural Core of Nivo FX Intelligence. 
        You now also manage the 'AI Stock Sentinel', an institutional-grade monitoring system for the AI and Semiconductor sectors (NVDA, TSM, ASML, ARM, etc.).
        
        Your Mission:
        - Analyze FX (OANDA) and AI Stocks (Alpaca).
        - Explain institutional concepts: HMM Regimes, QLSTM Probabilities, Whale Volume, and Lead Equipment Monitors.
        - Provide safe, risk-focused technical insights.
        - Maintain a highly professional, institutional, and 'cerebral' tone.
        """
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

        # Sub-modules accessible as attributes
        self.hmm = MarketRegimeDetector()
        self.lstm = NivoLSTM(pair=pair)  # Loads trained .pth if available
        self.order_book = OrderBookAnalyzer(oanda_token, oanda_id)

        # Auto-train HMM if data provided (threshold matches MarketRegimeDetector.MIN_TRAIN_SAMPLES)
        if data is not None and len(data) >= 150:
            returns = data['Close'].pct_change().dropna().values
            self.hmm.train(returns[-500:])

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
        Acts as the final gatekeeper. Disapproves of trades in turbulent regimes.
        """
        target = df if df is not None else self.data
        if target is None or len(target) < 100:
            return True, "SYSTEM VETO: Insufficient historical data for AI context."

        # Downcast to float32 for memory efficiency
        df_lite = target[['Close']].astype(np.float32)
        returns = df_lite['Close'].pct_change().dropna().values.flatten()

        if not self.hmm.is_trained:
            self.hmm.train(returns[-500:])

        regime = self.hmm.get_regime_string(target)

        # LSTM direction check
        status, prob = self.lstm.predict_next_move(target)

        veto = False
        reason = f"Regime: {regime} | AI Neural Vector: {'UPWARD' if prob > 50 else 'DOWNWARD'}"

        if regime == "HIGH_VOLATILITY":
            veto = True
            reason = "VETO: High Volatility detected (HMM)"
        elif regime == "CRASH_MODE":
            veto = True
            reason = "VETO: Market Crash / Extreme Panic (HMM)"

        return veto, reason

    def get_auto_execution_signal(self, df: pd.DataFrame, brain_analysis: dict):
        """
        Final decision engine for the Auto-Trader.
        Combines Technical Brain + AI Cortex Veto.
        """
        veto, reason = self.evaluate_veto(df)
        
        if veto:
            return "STANDBY", reason
            
        signal = brain_analysis.get("signal", "WAIT")
        
        if "BUY" in signal:
            return "EXECUTE_LONG", f"Cortex Approved | {reason}"
        elif "SELL" in signal:
            return "EXECUTE_SHORT", f"Cortex Approved | {reason}"
            
        return "STANDBY", "Brain Signal: WAIT"
