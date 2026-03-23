import os
import requests
import json
import logging
import pandas as pd
from v20 import Context
from v20.order import MarketOrderRequest
from v20.transaction import StopLossDetails, TrailingStopLossDetails

# Setup Logging
logger = logging.getLogger(__name__)

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
        self.last_order_id = None
        
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

    def has_open_position(self, instrument):
        """Checks if there is already an open position for the instrument."""
        try:
            response = self.ctx.position.get(self.account_id, instrument)
            # v20 Response status 404 means no position exists for this instrument
            if response.status != 200:
                return False
                
            position = response.get("position")
            if not position:
                return False
                
            long_units = float(getattr(position.long, "units", 0))
            short_units = float(getattr(position.short, "units", 0))
            return long_units != 0 or short_units != 0
        except Exception as e:
            # If we hit any other error (timeouts, etc), we return True to avoid double trading
            print(f"[ERROR] has_open_position check failed for {instrument}: {e}")
            return True 

    def get_position_performance(self, instrument):
        """Retrieves performance data for an open position."""
        try:
            response = self.ctx.position.get(self.account_id, instrument)
            if response.status != 200:
                return None
                
            position = response.get("position")
            if not position:
                return None
            
            long_units = float(getattr(position.long, "units", 0))
            short_units = float(getattr(position.short, "units", 0))
            
            if long_units != 0:
                units = long_units
                avg_price = float(getattr(position.long, "averagePrice", 0))
                trade_ids = getattr(position.long, "tradeIDs", [])
                trade_id = trade_ids[-1] if trade_ids else None
            elif short_units != 0:
                units = short_units
                avg_price = float(getattr(position.short, "averagePrice", 0))
                trade_ids = getattr(position.short, "tradeIDs", [])
                trade_id = trade_ids[-1] if trade_ids else None
            else:
                return None
            
            # Fetch current Hard Stop Loss
            sl_price = 0.0
            try:
                if trade_id:
                    trade_res = self.ctx.trade.get(self.account_id, trade_id)
                    if trade_res.status == 200:
                        trade_body = trade_res.get("trade")
                        sl_order = getattr(trade_body, "stopLossOrder", None)
                        if sl_order:
                            sl_price = float(getattr(sl_order, "price", 0))
            except Exception:
                pass
                
            # OANDA unrealizedPL is on the position object
            unrealized_pnl = float(getattr(position, "unrealizedPL", 0))
            
            # Fetch current prices
            pricing = self.ctx.pricing.get(self.account_id, instruments=instrument)
            if pricing.status != 200:
                return None
            prices = pricing.get("prices")
            if not prices:
                return None
            current_price = float(prices[0].closeoutBid if units < 0 else prices[0].closeoutAsk)
            
            # Fetch Trailing Stop level (Dynamic Exit)
            exit_price = 0.0
            try:
                orders_res = self.ctx.order.list_pending(self.account_id)
                if orders_res.status == 200:
                    pending_orders = orders_res.get("orders")
                    for o in pending_orders:
                        if getattr(o, 'instrument', '') == instrument and o.type == "TRAILING_STOP_LOSS":
                            exit_price = float(getattr(o, 'trailingStopValue', 0))
                            break
            except Exception:
                pass # Silently fail for TS if not found
            
            # Simple pip calculation (assumes 0.0001 or 0.01 for JPY)
            multiplier = 100 if "JPY" in instrument or "XAU" in instrument else 10000
            pips = (current_price - avg_price) * multiplier if units > 0 else (avg_price - current_price) * multiplier
            
            # INSURED PIPS calculation (Distance from Entry to current Stop Loss)
            insured_pips = 0.0
            if sl_price > 0:
                if units > 0: insured_pips = (sl_price - avg_price) * multiplier
                else: insured_pips = (avg_price - sl_price) * multiplier
            
            return {
                "trade_id": trade_id,
                "units": units,
                "entry_price": avg_price,
                "current_price": current_price,
                "exit_price": exit_price,
                "sl_price": sl_price,
                "pips": pips,
                "insured_pips": insured_pips,
                "pnl_usd": unrealized_pnl
            }
        except Exception as e:
            print(f"[ERROR] get_position_performance failed for {instrument}: {e}")
            return None

    def execute_trade(self, instrument, units, stop_loss_price, trailing_stop_distance=0.0020):
        """
        Layer 1 & 2: Execution with Hard Stop Loss and Trailing Stop.
        """
        if self.check_daily_kill_switch():
            return {"status": "error", "message": "Kill switch active"}
            
        if self.has_open_position(instrument):
            return {"status": "error", "message": f"Already have an open position for {instrument}"}

        try:
            # 1. Fetch Current Pricing to check Spread (Safety First)
            pricing_res = self.ctx.pricing.get(self.account_id, instruments=instrument)
            if pricing_res.status != 200:
                return {"status": "error", "message": f"Could not fetch pricing for spread check: {pricing_res.status}"}
            
            price_obj = pricing_res.get("prices")[0]
            curr_ask = float(price_obj.closeoutAsk)
            curr_bid = float(price_obj.closeoutBid)
            spread = abs(curr_ask - curr_bid)
            entry_price = curr_ask if int(units) > 0 else curr_bid
            
            # 2. Verify Stop Loss distance vs Spread
            # OANDA requires SL to be outside the spread. 
            # We enforce a buffer (Spread * 1.5 or at least 2 pips)
            decimals = 3 if "JPY" in instrument or "XAU" in instrument else 5
            pip_value = 0.01 if "JPY" in instrument or "XAU" in instrument else 0.0001
            min_buffer = max(spread * 1.5, pip_value * 2.0)
            
            sl_distance = abs(entry_price - float(stop_loss_price))
            
            actual_sl_price = float(stop_loss_price)
            if sl_distance < min_buffer:
                # Adjust SL to a safe distance
                if int(units) > 0: # Buy
                    actual_sl_price = entry_price - min_buffer
                else: # Sell
                    actual_sl_price = entry_price + min_buffer
                
                logger.warning(f"⚠️ [SL ADJUST] SL distance ({sl_distance:.{decimals}f}) < spread buffer ({min_buffer:.{decimals}f}). Adjusted SL to {actual_sl_price:.{decimals}f}")

            # 3. Dynamic Precision based on instrument type
            sl_price_str = f"{float(actual_sl_price):.{decimals}f}"
            
            # Ensure safe trailing stop distance
            safe_trailing_dist = abs(float(trailing_stop_distance))
            # Trailing stop must also be >= spread (usually)
            if safe_trailing_dist < min_buffer:
                safe_trailing_dist = min_buffer
                logger.warning(f"⚠️ [TS ADJUST] TS distance ({trailing_stop_distance}) < spread buffer. Adjusted to {safe_trailing_dist:.{decimals}f}")
            
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
            
            if response.status != 201:
                return {"status": "error", "message": getattr(response, "errorMessage", f"HTTP {response.status}")}
            
            body = getattr(response, "body", {})
            
            # 1. Check for Filling
            fill = body.get("orderFillTransaction")
            if fill:
                self.last_order_id = fill.id if hasattr(fill, "id") else getattr(fill, "id", "UnknownID")
                return {"status": "success", "order_id": self.last_order_id}
            
            # 2. Check for Immediate Cancellation
            cancel = body.get("orderCancelTransaction")
            if cancel:
                reason = getattr(cancel, "reason", "UNKNOWN_CANCELLATION")
                return {"status": "error", "message": f"Order Cancelled: {reason}"}
                
            return {"status": "error", "message": "Order 201 Created but no Fill/Cancel transaction found in body."}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_step_trailing(self, instrument, trade_id, entry_price, current_sl, units, current_pips):
        """Moves Stop Loss to lock in profit once a +30 pip threshold is reached."""
        try:
            # Nuevo Ajuste Estratégico (User Request):
            # Asegurar ganancias más rápido por condiciones erráticas del mercado.
            # "Asegurar un poco en +12 pips, y asegurar +10 pips pasados los 20 pips"
            
            if current_pips < 12.0: 
                return # No movemos nada hasta llegar a +12 pips
            
            # Si pasamos los 12 pips, aseguramos al menos +2 pips (Break-even + micro ganancia)
            # Pasados los 20 pips, aseguraremos el excedente menos un buffer de 10 pips.
            if current_pips < 20.0:
                locked_in_pips = 2.0
            else:
                locked_in_pips = current_pips - 10.0
            
            decimals = 3 if "JPY" in instrument else 5
            multiplier = 100 if "JPY" in instrument or "XAU" in instrument else 10000
            
            # Target SL Price
            if units > 0: # Buy
                target_sl = entry_price + (locked_in_pips / multiplier)
            else: # Sell
                target_sl = entry_price - (locked_in_pips / multiplier)
            
            # Round target SL to proper precision
            target_sl = round(target_sl, decimals)
            
            # Check if current SL is already better than target SL or at entry
            if units > 0: # Buy
                if current_sl >= target_sl: return # No change needed
            else: # Sell
                if current_sl > 0 and current_sl <= target_sl: return # No change needed


            print(f"[STEP TRAILING] Locking in +{locked_in_pips} pips for {instrument} (Target SL: {target_sl})")
            
            from v20.transaction import StopLossDetails
            sl_price_str = f"{target_sl:.{decimals}f}"
            
            response = self.ctx.trade.set_dependent_orders(
                self.account_id,
                trade_id,
                stopLoss=StopLossDetails(price=sl_price_str)
            )
            
            if response.status == 200:
                print(f"[STEP TRAILING] SL locked successfully for {instrument}")
                return True
                
        except Exception as e:
            print(f"[ERROR] update_step_trailing failed: {e}")
            return False

    def close_all_positions(self):
        """Emergency: Closes ALL open positions in the account using direct REST API."""
        try:
            logger.warning("🚨 [EMERGENCY] Closing ALL open positions via REST...")
            
            base_url = f"https://{self.hostname}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            # 1. Cancel all pending orders first to prevent ghost executions
            try:
                orders_req = requests.get(
                    f"{base_url}/v3/accounts/{self.account_id}/pendingOrders",
                    headers=headers, timeout=10
                )
                pending_orders = orders_req.json().get("orders", [])
                for order in pending_orders:
                    order_id = order.get("id")
                    if order_id:
                        requests.put(
                            f"{base_url}/v3/accounts/{self.account_id}/orders/{order_id}/cancel",
                            headers=headers, timeout=5
                        )
                logger.info(f"[KILL] Canceled {len(pending_orders)} pending orders.")
            except Exception as e:
                logger.error(f"[KILL] Error canceling pending orders: {e}")

            # 2. Fetch all open positions
            r = requests.get(
                f"{base_url}/v3/accounts/{self.account_id}/openPositions",
                headers=headers, timeout=10
            )
            positions = r.json().get("positions", [])
            
            if not positions and not pending_orders:
                return {"status": "success", "message": "No open positions or pending orders found"}
            
            results = []
            for pos in positions:
                instrument = pos["instrument"]
                long_units = float(pos["long"]["units"])
                short_units = float(pos["short"]["units"])
                
                # Determine which side to close
                if long_units > 0:
                    body = {"longUnits": "ALL", "shortUnits": "NONE"}
                elif short_units < 0:
                    body = {"longUnits": "NONE", "shortUnits": "ALL"}
                else:
                    continue
                
                res = requests.put(
                    f"{base_url}/v3/accounts/{self.account_id}/positions/{instrument}/close",
                    headers=headers, json=body, timeout=10
                )
                
                tx = res.json().get("shortOrderFillTransaction") or res.json().get("longOrderFillTransaction") or {}
                pl = float(tx.get("pl", 0)) if tx else 0.0
                results.append({"instrument": instrument, "status": res.status_code, "pl": pl})
                logger.info(f"[KILL] Closed {instrument}: HTTP {res.status_code} | PnL ${pl:+.2f}")
            
            return {"status": "success", "closed": results}
            
        except Exception as e:
            logger.error(f"[ERROR] close_all_positions failed: {e}")
            return {"status": "error", "message": str(e)}

    def close_single_position(self, instrument: str):
        """
        Closes a single position by instrument name (e.g. 'EUR_USD').
        Returns dict with status and realized PnL.
        """
        try:
            instrument = instrument.replace("/", "_").upper()
            logger.warning(f"📤 [CLOSE] Closing position for {instrument}...")

            base_url = f"https://{self.hostname}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            # Fetch position to determine side
            r = requests.get(
                f"{base_url}/v3/accounts/{self.account_id}/positions/{instrument}",
                headers=headers, timeout=10
            )
            if r.status_code != 200:
                return {"status": "error", "message": f"Could not fetch position: HTTP {r.status_code}"}

            pos = r.json().get("position", {})
            long_units = float(pos.get("long", {}).get("units", 0))
            short_units = float(pos.get("short", {}).get("units", 0))

            if long_units > 0:
                body = {"longUnits": "ALL", "shortUnits": "NONE"}
            elif short_units < 0:
                body = {"longUnits": "NONE", "shortUnits": "ALL"}
            else:
                return {"status": "error", "message": f"No open position for {instrument}"}

            res = requests.put(
                f"{base_url}/v3/accounts/{self.account_id}/positions/{instrument}/close",
                headers=headers, json=body, timeout=10
            )

            tx = res.json().get("shortOrderFillTransaction") or res.json().get("longOrderFillTransaction") or {}
            pl = float(tx.get("pl", 0)) if tx else 0.0
            logger.info(f"[CLOSE] {instrument}: HTTP {res.status_code} | PnL ${pl:+.2f}")

            if res.status_code in (200, 201):
                return {"status": "success", "instrument": instrument, "pl": pl}
            else:
                return {"status": "error", "message": f"OANDA HTTP {res.status_code}: {res.text[:200]}"}

        except Exception as e:
            logger.error(f"[ERROR] close_single_position failed: {e}")
            return {"status": "error", "message": str(e)}

    def calculate_position_size(self, instrument: str, stop_loss_pips: float):
        """Calculate units based on fixed Risk USD (Volatility Parity) and Stop Loss distance."""
        try:
            # 1. Get Account Balance
            response = self.ctx.account.summary(self.account_id)
            if response.status != 200:
                logger.error(f"Could not fetch account summary for sizing: {response.status}")
                return 1000
                
            account_summary = response.get("account")
            balance = float(account_summary.balance)
            
            # 2. Volatility Parity: Define Risk Amount
            # We use $20 USD as the default fixed risk per trade as per the V4 Institutional Plan
            fixed_risk_env = os.getenv("RISK_PER_TRADE_USD", "20.0")
            risk_amount = float(fixed_risk_env)
            
            # 3. Pip Multiplier (JPY vs Others)
            # For sizing: Units = Risk_Amount / (SL_Pips * Pip_Value_Per_Unit)
            multiplier = 0.01 if "JPY" in instrument else 0.0001
            
            # 4. Final Sizing
            if stop_loss_pips <= 0:
                logger.warning(f"Invalid SL pips ({stop_loss_pips}) for sizing. Using minimum.")
                return 1000
                
            units = int(risk_amount / (stop_loss_pips * multiplier))
            
            # Safety Cap: Don't leverage more than 20:1 on a single trade
            margin_cap = int(balance * 20)
            final_units = min(max(units, 1), margin_cap)
            
            logger.info(f"📊 [VOLATILITY PARITY] Balance: ${balance:.2f} | Risk: ${risk_amount:.2f} | SL Distance: {stop_loss_pips:.1f} pips | Sized Units: {final_units}")
            return final_units
            
        except Exception as e:
            logger.error(f"Error in calculate_position_size: {e}")
            return 1000 # Default micro-lot for safety
