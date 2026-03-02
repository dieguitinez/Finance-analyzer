import numpy as np
import pandas as pd
import torch
import torch.nn as nn
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    class GaussianHMM:
        def __init__(self, *args, **kwargs): pass
        def fit(self, *args, **kwargs): pass
        def predict(self, *args, **kwargs): return [0]
    HMM_AVAILABLE = False
import requests
import warnings
import gc

# Suppress standard convergence warnings for cleaner console output
warnings.filterwarnings("ignore")


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

    def __init__(self):
        self.model = GaussianHMM(n_components=3, covariance_type="full", n_iter=100)
        self.is_trained = False

    def train(self, returns: np.ndarray):
        """Train HMM on cleaned return series."""
        # Ensure 1D for Series conversion
        rt_flat = returns.flatten() if hasattr(returns, "flatten") else returns
        clean = pd.Series(rt_flat).replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 100:
            self.is_trained = False
            return
        data = clean.values.astype(np.float32).reshape(-1, 1)
        try:
            self.model.fit(data)
            self.is_trained = True
        except Exception as e:
            # HMM convergence errors or zero variance issues
            self.is_trained = False
            print(f"HMM Training Warning: {e}")

    def detect_regime(self, df: pd.DataFrame):
        """
        Returns (regime_id: int, regime_description: str).
        This is the method app.py calls via cortex.hmm.detect_regime(data).
        """
        if not self.is_trained:
            returns = df['Close'].pct_change().dropna().values.flatten()
            if len(returns) >= 100:
                self.train(returns[-500:])

        if not self.is_trained:
            return -1, "Unknown (Insufficient Data)"

        returns = df['Close'].pct_change().dropna().values
        rt_flat = returns.flatten() if hasattr(returns, "flatten") else returns
        clean = pd.Series(rt_flat).replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) == 0:
            return -1, "Unknown"

        data = clean.values.astype(np.float32).reshape(-1, 1)
        try:
            hidden_states = self.model.predict(data)
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
    """Lightweight LSTM architecture for CPU execution."""
    def __init__(self, input_size=1, hidden_layer_size=32, output_size=1):
        super(CPUOptimizedLSTM, self).__init__()
        self.input_size = input_size
        self.hidden_layer_size = hidden_layer_size
        self.lstm = nn.LSTM(input_size, hidden_layer_size, batch_first=True)
        self.linear = nn.Linear(hidden_layer_size, output_size)

    def forward(self, input_seq):
        # Convert to float32 tensor
        if not isinstance(input_seq, torch.Tensor):
            input_seq = torch.tensor(input_seq, dtype=torch.float32)
        else:
            input_seq = input_seq.float()

        if input_seq.dim() == 4:
            input_seq = input_seq.squeeze()
        
        if input_seq.dim() == 1:
            input_seq = input_seq.view(1, -1, self.input_size)
        elif input_seq.dim() == 2:
            input_seq = input_seq.unsqueeze(2) if self.input_size == 1 else input_seq.view(1, -1, self.input_size)

        try:
            lstm_out, _ = self.lstm(input_seq)
        except ValueError:
            input_seq = input_seq.view(1, -1, self.input_size)
            lstm_out, _ = self.lstm(input_seq)
            
        predictions = self.linear(lstm_out[:, -1, :])
        return predictions


class NivoLSTM:
    """
    LSTM predictor wrapper.
    Provides predict_next_move(df) -> (status_str, probability_float)
    which is what app.py calls via cortex.lstm.predict_next_move(data).
    """
    def __init__(self):
        self.model = CPUOptimizedLSTM()
        self.model.eval()

    def predict_next_move(self, df: pd.DataFrame):
        """
        Returns (status_string, bull_probability_float).
        e.g. ("Bullish Momentum", 67.3) or ("Bearish Pressure", 32.1)
        """
        try:
            close = df['Close'].values.astype(np.float32)
            if len(close) < 20:
                return "Insufficient Data", 50.0

            # Normalize last 20 candles
            seq = close[-20:]
            seq_norm = ((seq - np.mean(seq)) / (np.std(seq) + 1e-8)).astype(np.float32)

            with torch.no_grad():
                tensor = torch.from_numpy(seq_norm).unsqueeze(0).unsqueeze(-1)
                prediction = self.model(tensor).item()

            # Convert raw output to probability
            bull_prob = float(np.clip(50.0 + prediction * 100, 5.0, 95.0))

            if bull_prob > 55:
                status = "Bullish Momentum"
            elif bull_prob < 45:
                status = "Bearish Pressure"
            else:
                status = "Neutral / Indecisive"

            return status, round(bull_prob, 1)
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
    def __init__(self, data: pd.DataFrame = None, oanda_token: str = "", oanda_id: str = ""):
        self.data = data
        self.oanda_token = oanda_token
        self.oanda_id = oanda_id

        # Sub-modules accessible as attributes
        self.hmm = MarketRegimeDetector()
        self.lstm = NivoLSTM()
        self.order_book = OrderBookAnalyzer(oanda_token, oanda_id)

        # Auto-train HMM if data provided
        if data is not None and len(data) >= 100:
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
