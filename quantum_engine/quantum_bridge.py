import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import gc
import os
import json

class QuantumBridge:
    def __init__(self):
        """
        Integration layer for Nivo FX Intelligence Suite merging classical
        and quantum mathematical pipelines.
        """
        # Self-Learning Logic
        self.lessons_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lessons_learned.json")
        self.feedback_data = self._load_learning_feedback()

        # Dictionary for Bilingual UI Compatibility
        self.ui_text = {
            "en": {
                "chart_title": "Classical vs Quantum Score Convergence",
                "x_axis": "Time Steps",
                "y_axis": "Normalized Score",
                "leg_tech": "Legacy Tech Score",
                "leg_fund": "Legacy Fund Score",
                "q_delta": "Quantum Forecast Delta",
                "final_q": "Final Nivo Q-Score"
            },
            "es": {
                "chart_title": "Convergencia de Puntuación Clásica vs Cuántica",
                "x_axis": "Pasos de Tiempo",
                "y_axis": "Puntuación Normalizada",
                "leg_tech": "Puntuación Técnica Legacy",
                "leg_fund": "Puntuación Fundamental Legacy",
                "q_delta": "Delta de Previsión Cuántica",
                "final_q": "Puntuación Final Nivo Q"
            }
        }

    def _load_learning_feedback(self):
        """Loads recent performance metadata to adjust thresholds."""
        if os.path.exists(self.lessons_path):
            try:
                with open(self.lessons_path, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def execute_pipeline(self, data: pd.DataFrame) -> dict:
        """
        Full analysis pipeline that app.py invokes.
        Performs lightweight regime detection and momentum scoring using float32
        arrays for minimal memory footprint.
        
        Args:
            data (pd.DataFrame): OHLCV DataFrame with 'Close', 'High', 'Low' columns.
            
        Returns:
            dict with keys: quantum_multiplier, hqmm_probs, qlstm_bull_prob, optimal_position_size
        """
        try:
            close = data['Close'].values.astype(np.float32)
            
            if len(close) < 20:
                return self._default_result()
            
            # --- 1. HQMM Regime Detection (via rolling volatility proxy) ---
            returns = np.diff(close) / (close[:-1] + 1e-8)
            rolling_window = min(20, len(returns))
            rolling_std = np.array([
                np.std(returns[max(0, i - rolling_window):i + 1])
                for i in range(len(returns))
            ], dtype=np.float32)
            
            current_vol = rolling_std[-1] if len(rolling_std) > 0 else 0.01
            median_vol = np.median(rolling_std) if len(rolling_std) > 0 else 0.01
            
            # Classify regime probabilistically
            vol_ratio = current_vol / (median_vol + 1e-8)
            if vol_ratio < 0.8:
                hqmm_probs = [0.65, 0.25, 0.10]  # Low Vol dominant
            elif vol_ratio > 1.5:
                hqmm_probs = [0.10, 0.25, 0.65]  # Chaotic dominant
            else:
                hqmm_probs = [0.20, 0.60, 0.20]  # Trending dominant
            
            # --- 2. QLSTM Bull Probability (via EMA momentum proxy) ---
            ema_fast = self._ema(close, 12)
            ema_slow = self._ema(close, 26)
            momentum = (ema_fast - ema_slow) / (ema_slow + 1e-8)
            bull_prob = float(np.clip(0.5 + momentum * 10, 0.05, 0.95))
            
            # --- 3. Quantum Multiplier (confidence-weighted) ---
            trend_strength = abs(momentum)
            if hqmm_probs[2] > 0.5:
                # Chaotic regime: dampen multiplier to protect capital
                q_multiplier = max(0.6, 1.0 - trend_strength * 2)
            elif hqmm_probs[1] > 0.4:
                # Trending regime: boost multiplier
                q_multiplier = min(1.4, 1.0 + trend_strength * 3)
            else:
                # Low vol: neutral
                q_multiplier = 1.0
            
            # --- 4. Optimal Position Size (Symmetric Conviction) ---
            # Distance from 0.5 (Neutral) represents conviction regardless of direction
            conviction = abs(bull_prob - 0.5) * 2.0
            position_size = float(np.clip(q_multiplier * (1.0 + conviction), 0.25, 2.0))
            
            result = {
                'quantum_multiplier': round(float(q_multiplier), 4),
                'hqmm_probs': [round(p, 4) for p in hqmm_probs],
                # ✅ FIX: Return in 0-100 scale (was 0-1) to match expected scale in calculate_nivo_q_score
                'qlstm_bull_prob': round(bull_prob * 100, 2),
                'optimal_position_size': round(position_size, 4),
            }
            
        except Exception:
            result = self._default_result()
        
        gc.collect()
        return result
    
    def _ema(self, data: np.ndarray, period: int) -> float:
        """Compute final EMA value using float32 for memory savings."""
        if len(data) < period:
            return float(np.mean(data))
        alpha = np.float32(2.0 / (period + 1))
        ema = np.float32(data[0])
        for val in data[1:]:
            ema = alpha * np.float32(val) + (1 - alpha) * ema
        return float(ema)
    
    def _default_result(self) -> dict:
        """Fallback result when data is insufficient."""
        return {
            'quantum_multiplier': 1.0,
            'hqmm_probs': [0.33, 0.34, 0.33],
            'qlstm_bull_prob': 0.5,
            'optimal_position_size': 1.0,
        }

    def calculate_nivo_q_score(self, legacy_tech_score: float, legacy_fund_score: float, 
                             q_regime_state: int, q_forecast_delta: float, q_position_weight: float) -> float:
        """
        Merges input scores using Symmetric Differential Math (Distance from 50).
        Ensures both LONG and SHORT signals are amplified equally.
        """
        # --- 1. Base Classical Differential ---
        tech_diff = legacy_tech_score - 50.0
        fund_diff = legacy_fund_score - 50.0
        base_diff = (tech_diff * 0.6) + (fund_diff * 0.4)
        
        # --- 2. Soros Reflexivity Multiplier ---
        reflex_mult = 1.0
        is_bull = base_diff > 5.0
        is_bear = base_diff < -5.0
        
        # If technicals and fundamentals align in the same direction
        if (tech_diff > 5 and fund_diff > 5) or (tech_diff < -5 and fund_diff < -5):
            reflex_mult = 1.3  # Boost conviction on alignment
        elif (tech_diff * fund_diff) < 0:
            reflex_mult = 0.7  # Dampen conviction on divergence
            
        # --- 3. Quantum Phase Integration ---
        q_diff = q_forecast_delta - 50.0
        if q_regime_state == 0:
            # Low Volatility (most bullish regime): keep base_diff intact.
            # Only dampen the noisy quantum component to avoid overreacting to calm markets.
            # BUG FIX: Previously applied base_diff *= 0.8 here which artificially
            # suppressed bullish scores in the calmest regime → SELL bias introduced.
            q_impact = q_diff * 0.3
        else:
            # Trending / Crash regime: boost quantum impact for stronger conviction
            q_impact = q_diff * 0.7
            
        # --- 4. Final Aggregation & Weighting ---
        final_diff = (base_diff + q_impact) * q_position_weight * reflex_mult
        
        # Map back to 0-100 range (50 is neutral)
        actual_score = 50.0 + final_diff
        
        # --- 5. Self-Learning Adjustment ---
        # If recent performance was bad, we apply a 'Safety Buffer' (dynamic thresholding)
        learning_adj = 0.0
        if self.feedback_data:
            learning_adj = self.feedback_data.get("threshold_adjustment", 0.0)
            
        # Optimization: We only 'harden' the score if it was already close to a signal
        # For example, if score is 60 and adjustment is 5, we make it 55 to filter it out.
        adjusted_score = actual_score - learning_adj if actual_score > 50 else actual_score + learning_adj
        
        return float(np.clip(adjusted_score, 0.0, 100.0))

    def plot_bridge_convergence(self, history_df: pd.DataFrame, lang: str = "en") -> go.Figure:
        """
        Outputs a visualization of how legacy scores and quantum scores merge over time.
        
        Args:
            history_df (pd.DataFrame): Must contain ['tech_score', 'fund_score', 'q_delta', 'final_score']
            lang (str): 'en' or 'es' for bilingual titles.
            
        Returns:
            plotly.graph_objects.Figure
        """
        # Fallback to English if unknown language passed
        t = self.ui_text.get(lang.lower(), self.ui_text['en'])
        
        # Pure manual vectorization / smoothing for visual curve aesthetics (NO pandas-ta)
        if not history_df.empty and len(history_df) >= 3:
            # Generating a simple SMA proxy for the final score mechanically using numpy convolve
            window = min(3, len(history_df))
            weights = np.ones(window) / window
            smoothed_final = np.convolve(history_df['final_score'].values, weights, mode='valid')
            # Pad the beginning so the array length matches the dataframe index
            padding = np.full(window - 1, np.nan)
            history_df['smoothed_final'] = np.concatenate((padding, smoothed_final))
        else:
            history_df['smoothed_final'] = history_df['final_score'] if not history_df.empty else []

        fig = go.Figure()
        
        if not history_df.empty:
            x_vals = history_df.index
            
            # Classical Traces
            fig.add_trace(go.Scatter(x=x_vals, y=history_df['tech_score'], 
                                     mode='lines', line=dict(color='gray', width=1, dash='dot'),
                                     name=t['leg_tech']))
            fig.add_trace(go.Scatter(x=x_vals, y=history_df['fund_score'], 
                                     mode='lines', line=dict(color='silver', width=1, dash='dot'),
                                     name=t['leg_fund']))
                                     
            # Quantum Traces
            fig.add_trace(go.Scatter(x=x_vals, y=history_df['q_delta'], 
                                     mode='lines', line=dict(color='purple', width=1.5),
                                     name=t['q_delta']))
                                     
            # Final Merged Convergence
            fig.add_trace(go.Scatter(x=x_vals, y=history_df['smoothed_final'], 
                                     mode='lines', line=dict(color='cyan', width=3),
                                     name=t['final_q']))
                                     
        fig.update_layout(
            title=t['chart_title'],
            xaxis_title=t['x_axis'],
            yaxis_title=t['y_axis'],
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        return fig
