import os
import requests
import json
import pandas as pd
from v20 import Context
from v20.order import MarketOrderRequest
from v20.transaction import StopLossDetails, TrailingStopLossDetails

class NivoAutoTrader:
    """
    Nivo FX Auto-Trader with Three-Layer Risk Architecture.
    Handles execution on OANDA via v20 API.
    """
    def __init__(self, token, account_id, environment="practice"):
        self.token = token
        self.account_id = account_id
        self.hostname = "api-fxpractice.oanda.com" if environment == "practice" else "api-fxtrade.oanda.com"
        self.ctx = Context(self.hostname, 443, ssl=True, token=token)
        
        # Risk Settings
        self.max_daily_drawdown_pct = 2.0  # Layer 3: Kill Switch at 2% loss
        self.capital_at_risk_per_trade = 0.01  # 1% per trade
        self.starting_daily_balance: float = 0.0
        self.min_signal_strength = 60  # The "Trigger" percentage
        
    def check_daily_kill_switch(self):
        """Layer 3: Check if we hit the daily drawdown limit."""
        try:
            response = self.ctx.account.summary(self.account_id)
            account_summary = response.get("account", 200)
            current_balance = float(account_summary.balance)
            
            if self.starting_daily_balance <= 0:
                self.starting_daily_balance = current_balance
                return False
                
            loss_pct = ((self.starting_daily_balance - current_balance) / self.starting_daily_balance) * 100
            
            if loss_pct >= self.max_daily_drawdown_pct:
                print(f"🛑 KILL SWITCH TRIGGERED: Daily loss {loss_pct:.2f}% exceeds limit.")
                return True
            return False
        except Exception as e:
            print(f"Error checking kill switch: {e}")
            return True # Veto on error for safety

    def execute_trade(self, instrument, units, stop_loss_price, trailing_stop_distance=0.0020):
        """
        Layer 1 & 2: Execution with Hard Stop Loss and Trailing Stop.
        """
        if self.check_daily_kill_switch():
            return {"status": "error", "message": "Kill switch active"}

        try:
            # Dynamic Precision based on instrument type (JPY pairs = 3 decimals, Others = 5 decimals)
            decimals = 3 if "JPY" in instrument else 5
            
            # Ensure price string formatting matches OANDA exact requirements (e.g. '1.14000' not '1.14')
            sl_price_str = f"{float(stop_loss_price):.{decimals}f}"
            
            # OANDA Rule: Trailing Stop Distance must be SMALLER than the actual Stop Loss distance
            # If both are 1.5 ATR, it causes STOP_LOSS_ON_FILL_LOSS rejection. We force TS to be 0.6x the provided distance.
            safe_trailing_dist = abs(float(trailing_stop_distance)) * 0.6
            ts_dist_str = f"{safe_trailing_dist:.{decimals}f}"
            
            # Prepare Order with Layer 1 (Stop Loss) and Layer 2 (Trailing Stop)
            order_request = MarketOrderRequest(
                instrument=instrument,
                units=int(units),
                stopLossOnFill=StopLossDetails(price=sl_price_str),
                trailingStopLossOnFill=TrailingStopLossDetails(distance=ts_dist_str)
            )
            
            response = self.ctx.order.market(self.account_id, **order_request.dict())
            
            # DEBUG: Show raw response status
            print(f"[DEBUG] OANDA Status: {response.status}")
            
            # OANDA returns 201 for Created, but the order might not be Filled (it might be Cancelled)
            if response.status != 201:
                return {"status": "error", "message": getattr(response, "errorMessage", f"HTTP {response.status}")}
            
            # Accessing from response.body directly for absolute dictionary-key precision
            body = getattr(response, "body", {})
            
            # 1. Check for Filling
            fill = body.get("orderFillTransaction")
            if fill:
                return {"status": "success", "order_id": fill.id if hasattr(fill, "id") else getattr(fill, "id", "UnknownID")}
            
            # 2. Check for Immediate Cancellation
            cancel = body.get("orderCancelTransaction")
            if cancel:
                reason = getattr(cancel, "reason", "UNKNOWN_CANCELLATION")
                return {"status": "error", "message": f"Order Cancelled: {reason}"}
                
            return {"status": "error", "message": "Order 201 Created but no Fill/Cancel transaction found in body."}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_position_size(self, stop_loss_pips):
        """Calculate units based on risk percentage and stop loss distance."""
        # Simplified for EUR/USD. In production, this would account for exchange rates.
        try:
            response = self.ctx.account.summary(self.account_id)
            balance = float(response.get("account").balance)
            risk_amount = balance * self.capital_at_risk_per_trade
            
            # 1 pip = 0.0001 (for EUR/USD)
            pip_value = 10  # Standard lot (100k) pip value is $10
            # risk_amount / (stop_loss_pips * pip_value_per_unit)
            # This is a placeholder for actual math which depends on currency
            units = int(risk_amount / (stop_loss_pips * 0.0001))
            return units
        except:
            return 1000 # Default micro-lot for safety
