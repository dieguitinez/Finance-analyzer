import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import gc

class QuantumBridge:
    def __init__(self):
        """
        Integration layer for Nivo FX Intelligence Suite merging classical
        and quantum mathematical pipelines.
        """
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
            
            # --- 4. Optimal Position Size ---
            position_size = float(np.clip(q_multiplier * bull_prob * 2, 0.25, 2.0))
            
            result = {
                'quantum_multiplier': round(float(q_multiplier), 4),
                'hqmm_probs': [round(p, 4) for p in hqmm_probs],
                'qlstm_bull_prob': round(bull_prob, 4),
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
        Merges input scores mathematically to return the final_nivo_q_score.
        Implements Soros 'Reflexivity' via a convergence multiplier.
        
        Args:
            legacy_tech_score (float): Technical analysis score (0-100).
            legacy_fund_score (float): Fundamental sentiment score (0-100).
            q_regime_state (int): HMM state (0=ranging, 1=trending).
            q_forecast_delta (float): LSTM bull probability (0-100).
            q_position_weight (float): Risk-based leverage multiplier.
            
        Returns:
            float: The finalized blend score (0-100).
        """
        # --- 1. Base Classical Blend ---
        base_classical = (legacy_tech_score * 0.6) + (legacy_fund_score * 0.4)
        
        # --- 2. Soros Reflexivity Multiplier ---
        # Neutral zone is around 50. We look for alignment or divergence.
        reflex_mult = 1.0
        
        is_tech_bull = legacy_tech_score > 55
        is_tech_bear = legacy_tech_score < 45
        is_fund_bull = legacy_fund_score > 55
        is_fund_bear = legacy_fund_score < 45

        if (is_tech_bull and is_fund_bull) or (is_tech_bear and is_fund_bear):
            # Synergistic Reflexivity (Feedback Loop)
            reflex_mult = 1.25
        elif (is_tech_bull and is_fund_bear) or (is_tech_bear and is_fund_bull):
            # Market Friction (Divergence)
            reflex_mult = 0.75
            
        # --- 3. Quantum Phase Integration ---
        if q_regime_state == 0:
            # Ranging: protect capital, lower delta weight
            adjusted_delta = q_forecast_delta * 0.2
            base_classical *= 0.9 # Extra dampening for ranging noise
        else:
            # Trending: allocate more weight to quantum forecasts
            adjusted_delta = q_forecast_delta * 0.6
            
        # --- 4. Final Aggregation & Mapping ---
        # (Classical + Quantum) * Position Weight * Reflexivity Multiplier
        raw_final = (base_classical + adjusted_delta) * q_position_weight * reflex_mult
        
        # Normalize into 0-100 boundary
        return float(np.clip(raw_final, 0.0, 100.0))

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
