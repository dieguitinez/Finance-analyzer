import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

class CapitalGuardian:
    def __init__(self, max_daily_loss_pct: float = -2.0, max_position_size: float = 2.0):
        """
        Risk Management and Kill Switch module for the Nivo FX Intelligence Suite.
        """
        self.max_daily_loss_pct = max_daily_loss_pct        # Daily Loss Limit (Hard Stop)
        self.max_position_size = max_position_size          # Position Size Capping
        self.kill_switch_active = False                     # Kill Switch Status
        
        # Bilingual UI Hook
        self.ui_text = {
            "en": {
                "active": "✅ SYSTEM ACTIVE: Capital Guardian Monitoring",
                "halted": "🛑 SYSTEM HALTED: KILL SWITCH TRIGGERED (Max Drawdown Reached)",
                "chart_title": "Capital Guardian: Daily PnL vs Hard Stop",
                "x_axis": "Trades",
                "y_axis": "Daily PnL (%)",
                "pnl_line": "Cumulative Daily PnL",
                "hard_stop": "Hard Stop Limit (-{:.1f}%)",
                "hold_signal": "HOLD / CANCEL_ALL"
            },
            "es": {
                "active": "✅ SISTEMA ACTIVO: Guardián de Capital Monitoreando",
                "halted": "🛑 SISTEMA DETENIDO: INTERRUPTOR DE APAGADO ACTIVADO (Límite Alcanzado)",
                "chart_title": "Guardián de Capital: PnL Diario vs Límite Fijo",
                "x_axis": "Operaciones",
                "y_axis": "PnL Diario (%)",
                "pnl_line": "PnL Diario Acumulado",
                "hard_stop": "Límite de Pérdida Fija (-{:.1f}%)",
                "hold_signal": "ESPERAR / CANCELAR_TODO"
            }
        }

    def update_risk_metrics(self, trade_returns_pct: pd.Series):
        """
        Calculates moving PnL, drawdowns, and volatility using pure manual vectorization (No pandas-ta).
        Updates kill switch status if Hard Stop is breached.
        """
        if trade_returns_pct is None or trade_returns_pct.empty:
            return 0.0, 0.0, 0.0
            
        returns_array = trade_returns_pct.values
        
        # Pure Numpy Cumulative PnL
        cumulative_pnl = np.cumsum(returns_array)
        current_daily_pnl = cumulative_pnl[-1]
        
        # Pure Numpy Max Drawdown
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = running_max - cumulative_pnl
        max_drawdown = np.max(drawdown)
        
        # Pure Numpy Volatility (Standard Deviation of returns)
        volatility = np.std(returns_array) if len(returns_array) > 1 else 0.0
        
        # Deprecated: The user requested 24/7 analysis regardless of daily drawdown.
        # OANDA Stop Losses handle trade-level risk. The Kill Switch is now purely 
        # driven by the Telegram /detener command.
        # if current_daily_pnl <= self.max_daily_loss_pct:
        #     self.kill_switch_active = True
            
        return current_daily_pnl, max_drawdown, volatility

    def evaluate_trade(self, raw_signal: str, q_position_weight: float, current_daily_pnl_pct: float, lang: str = "en") -> tuple:
        """
        Gatekeeper intercepting signals before Execution.
        Returns: (final_signal, capped_position_weight, status_message)
        """
        t = self.ui_text.get(lang.lower(), self.ui_text['en'])
        
        # Re-check Hard Stop Limit just in case (disabled per user request for 24/7 uptime)
        # if current_daily_pnl_pct <= self.max_daily_loss_pct:
        #     self.kill_switch_active = True
            
        # 1. API Block
        if self.kill_switch_active:
            status = t['halted']
            final_signal = t['hold_signal']
            capped_weight = 0.0
            return final_signal, capped_weight, status
            
        # 2. Position Size Capping
        capped_weight = min(q_position_weight, self.max_position_size)
        capped_weight = max(0.1, capped_weight) # Ensure positive sizing if safe
        
        return raw_signal, capped_weight, t['active']

    def plot_risk_dashboard(self, pnl_history: list, lang: str = "en") -> go.Figure:
        """
        Visualizes the current Daily PnL against the Hard Stop limit using tightly configured Plotly visuals.
        """
        t = self.ui_text.get(lang.lower(), self.ui_text['en'])
        
        pnl_array = np.array(pnl_history)
        x_vals = np.arange(1, len(pnl_array) + 1)
        
        fig = go.Figure()
        
        # Choose line color dynamically
        current_pnl = pnl_array[-1] if len(pnl_array) > 0 else 0.0
        if current_pnl <= self.max_daily_loss_pct:
            line_color = 'red'
        elif current_pnl < 0:
            line_color = 'orange'
        else:
            line_color = 'limegreen'
            
        # Plotly Cumulative Pnl
        fig.add_trace(go.Scatter(
            x=x_vals, 
            y=pnl_array,
            mode='lines+markers',
            line=dict(color=line_color, width=3),
            marker=dict(size=6, color=line_color, symbol='circle'),
            name=t['pnl_line']
        ))
        
        # Hard Stop Threshold Line
        fig.add_hline(
            y=self.max_daily_loss_pct, 
            line_dash="dash", 
            line_color="red", 
            annotation_text=t['hard_stop'].format(abs(self.max_daily_loss_pct)), 
            annotation_position="bottom right"
        )
        
        # Zero Line
        fig.add_hline(y=0.0, line_color="gray", line_width=1, opacity=0.5)
        
        fig.update_layout(
            title=t['chart_title'],
            xaxis_title=t['x_axis'],
            yaxis_title=t['y_axis'],
            template="plotly_dark",
            hovermode="x unified",
            showlegend=True
        )
        
        return fig
