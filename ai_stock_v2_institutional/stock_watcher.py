import os
import time
import json
import logging
import requests
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta, timezone, date
import json

# Eastern Time for NYSE/NASDAQ — always use this for market hours detection
try:
    import zoneinfo
    _ET_TZ = zoneinfo.ZoneInfo("America/New_York")
except ImportError:
    _ET_TZ = timezone(timedelta(hours=-5))  # EST fallback (no auto-DST)
import logging
from logging.handlers import RotatingFileHandler

try:
    from telegram_notifier import StockTelegramNotifier
    from cerebral_engine import StockCerebralEngine
    from execution_engine import StockExecutionEngine
except ImportError:
    from ai_stock_sentinel.telegram_notifier import StockTelegramNotifier
    from ai_stock_sentinel.cerebral_engine import StockCerebralEngine
    from ai_stock_sentinel.execution_engine import StockExecutionEngine

import yfinance as yf

# Cargar configuración aislada — usar ruta absoluta para que funcione
# correctamente tanto como script directo como desde systemd service.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, '.env'))

# ─── PDT GUARD CONSTANTS ─────────────────────────────────────────────────────
# Archivo persistente para rastrear fechas de compra por símbolo
_PDT_TRACKER_FILE = "/tmp/nivo_stock_pdt_tracker.json"

# ─── SECTOR HEALTH CONSTANTS ──────────────────────────────────────────────────
# SOXX = iShares Semiconductor ETF. SPY = S&P 500
_SOXX_SYMBOL         = "SOXX"
_QQQ_SYMBOL          = "QQQ"
_SPY_SYMBOL          = "SPY"
_SECTOR_BEAR_THRESHOLD = -3.0   # Si SOXX baja más de 3% en el día → Cash mode
_MARKET_BEAR_THRESHOLD = -1.5   # Si QQQ baja más de 1.5% en el día → Cash mode

# Sanctuary Assets (Gold, Utilities, Bonds) to pivot to when tech collapses
_SANCTUARY_SYMBOLS = ["GLD", "XLU", "TLT"]

# ─── EARNINGS CALENDAR API ───────────────────────────────────────────────────
_EARNINGS_CACHE_FILE = "/tmp/nivo_earnings_cache.json"


class NivoStockWatcher:
    def __init__(self):
        # 🛡️ Configuración de Logs (Rotación Automática para evitar llenar el disco)
        log_file = 'sentinel.log'
        self.logger = logging.getLogger("StockSentinel")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.is_paper = os.getenv('ALPACA_PAPER', 'True') == 'True'

        # Clientes de Alpaca
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=self.is_paper)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)

        # Motores Nivo
        self.notifier = StockTelegramNotifier()
        self.cerebro = StockCerebralEngine()
        self.executor = StockExecutionEngine(self.trading_client)

        # Order Queue — persisted to disk so it survives crashes
        self._queue_file = "/tmp/nivo_stock_queue.json"
        self.order_queue = self._load_queue()
        self.watchlist = os.getenv('STOCK_WATCHLIST', 'NVDA,TSM').split(',')
        self.autonomous_mode = os.getenv('STOCK_AUTONOMOUS_MODE', 'True') == 'True'

        # Capital per trade basado en equity disponible (para notional orders)
        self._capital_per_trade = float(os.getenv('CAPITAL_PER_TRADE_USD', '20.0'))

        # PDT tracker — persiste fechas de compra entre reinicios del bot
        self._pdt_tracker = self._load_pdt_tracker()

        # Position cache — to detect broker-side closes (OCO/SL/TP hit)
        # Format: {"NVDA": {"qty": 0.15, "avg_entry": 130.50}}
        self._positions_cache_file = "/tmp/nivo_stock_positions_cache.json"
        self._positions_cache = self._load_positions_cache()

        self.logger.info(f"[INIT] Nivo AI Stock Sentinel iniciado. Modo paper: {self.is_paper}")
        self.logger.info(f"[WATCHLIST] Monitoreando {len(self.watchlist)} activos: {self.watchlist}")
        self.logger.info(f"[MODE] Autónomo: {'SÍ' if self.autonomous_mode else 'NO (Solo Alertas)'}")
        self.logger.info(f"[CAPITAL] Capital por trade: ${self._capital_per_trade}")

    # ─── PDT PROTECTION ───────────────────────────────────────────────────────

    def _load_pdt_tracker(self) -> dict:
        """Carga el registro de fechas de compra (para protección PDT)."""
        try:
            if os.path.exists(_PDT_TRACKER_FILE):
                with open(_PDT_TRACKER_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_pdt_tracker(self):
        """Persiste el registro de fechas de compra."""
        try:
            with open(_PDT_TRACKER_FILE, 'w') as f:
                json.dump(self._pdt_tracker, f)
        except Exception as e:
            self.logger.error(f"[PDT] Error guardando tracker: {e}")

    def record_purchase(self, symbol: str, entry_price: float, tp: float, sl: float):
        """Registra la compra con metadatos para transparencia en Telegram."""
        today = date.today().isoformat()
        self._pdt_tracker[symbol] = {
            "date": today,
            "entry_price": float(round(entry_price, 2)),
            "tp_target": float(round(tp, 2)),
            "sl_target": float(round(sl, 2))
        }
        self._save_pdt_tracker()
        self.logger.info(f"[PDT/Log] Compra registrada: {symbol} @ ${entry_price:.2f} (TP: {tp}, SL: {sl})")

    def is_pdt_safe_to_sell(self, symbol: str, is_emergency: bool = False) -> bool:
        """
        Intelligent PDT Protection:
        1. Si se compró ayer o antes, es seguro vender (no gasta count).
        2. Si se compró HOY:
           - Si no es una emergencia, BLOQUEAMOS para conservar los 3 tokens (Hold overnight).
           - Si es emergencia, gastamos un token (si quedan disponibles).
        """
        purchase_data = self._pdt_tracker.get(symbol)
        
        # Si no hay registro o no es de hoy, es una posición antigua (SAFE)
        if not purchase_data:
            return True
        
        # Soportar formato viejo (string) y nuevo (dict)
        if isinstance(purchase_data, dict):
            purchase_date_str = purchase_data.get("date")
        else:
            purchase_date_str = purchase_data
            
        if not purchase_date_str:
            return True
            
        purchase_date = date.fromisoformat(purchase_date_str)
        today = date.today()
        
        if purchase_date < today:
            return True  # Fue comprado ayer o antes, vender no cuenta como day trade

        # --- ES UN DAY TRADE (Comprado HOY) ---
        if not is_emergency:
            self.logger.info(f"⏳ [PDT GUARD] {symbol} comprado hoy. Retenido hasta mañana para no gastar token PDT en operaciones normales.")
            return False

        # --- ES UN DAY TRADE (Comprado HOY) ---
        try:
            # Recuperar historial local de day trades
            dt_history = self._pdt_tracker.get("__dt_history__", [])
            from datetime import timedelta
            
            # Retroceder exactamente 5 días hábiles
            business_days_counted = 0
            start_date = today
            while business_days_counted < 5:
                if start_date.weekday() < 5:  # 0=Lun, ..., 4=Vie
                    business_days_counted = business_days_counted + 1
                start_date -= timedelta(days=1)
                
            recent_dts = [d for d in dt_history if date.fromisoformat(d) > start_date]
            
            # Autolimpiar vieja historia
            self._pdt_tracker["__dt_history__"] = recent_dts
            self._save_pdt_tracker()
            
            dt_count = len(recent_dts)
            
            if dt_count < 3:
                # Ejecutamos el trade, sumar al tracker local
                self._pdt_tracker["__dt_history__"].append(today.isoformat())
                self._save_pdt_tracker()
                
                self.logger.info(
                    f"[PDT GUARD] [WARN] TOKEN DAY TRADE USADO para {symbol}. "
                    f"Fueron consumidos {int(dt_count) + 1}/3 (Locales)."
                )
                return True
            else:
                self.logger.warning(
                    f"[PDT GUARD] [FAIL] VENTA BLOQUEADA para {symbol}: "
                    f"MÁXIMO PDT ALCANZADO ({dt_count}/3 locales). "
                    f"La venta se pospone para mañana."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"[PDT GUARD] Error consultando Alpaca API: {e}. Bloqueando por seguridad.")
            return False

    # ─── EARNINGS FILTER ──────────────────────────────────────────────────────

    def _get_earnings_today_and_tomorrow(self) -> set:
        """
        Descarga la lista de compañías con reporte de earnings HOY o MAÑANA usando yfinance.
        Usa caché para optimizar las peticiones (TTL: 6 horas).
        """
        cache_path = _EARNINGS_CACHE_FILE
        now = datetime.now()

        # Intentar usar caché si tiene menos de 6 horas
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    cache = json.load(f)
                cached_at = datetime.fromisoformat(cache.get("cached_at", "2000-01-01"))
                if (now - cached_at).total_seconds() < 21600:  # 6h
                    return set(cache.get("symbols", []))
        except Exception:
            pass

        earnings_symbols = set()
        today_date = now.date()
        tomorrow_date = today_date + timedelta(days=1)
        
        symbols_to_check = self.watchlist + _SANCTUARY_SYMBOLS

        for symbol in symbols_to_check:
            # ETFs don't have corporate earnings, skip yfinance API calls directly.
            if symbol in _SANCTUARY_SYMBOLS:
                continue
                
            try:
                # Optimized yfinance calendar fetch
                ticker = yf.Ticker(symbol)
                cal = ticker.calendar
                if cal and 'Earnings Date' in cal and cal['Earnings Date']:
                    earnings_dates = cal['Earnings Date']
                    for ed in earnings_dates:
                        if ed == today_date or ed == tomorrow_date:
                            earnings_symbols.add(symbol)
                            break
            except Exception as e:
                if "404" not in str(e):
                    self.logger.warning(f"[EARNINGS] Error validando {symbol} via yfinance: {e}")

        # Guardar caché
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    "cached_at": now.isoformat(),
                    "symbols": list(earnings_symbols)
                }, f)
        except Exception:
            pass

        if earnings_symbols:
            self.logger.info(f"[EARNINGS] [CALENDAR] Reportes en las próximas 48h: {earnings_symbols}")

        return earnings_symbols

    def _get_daily_change_pct(self, symbol) -> float:
        """Obtiene el cambio porcentual diario aproximado usando las últimas 2 velas de 1 min."""
        try:
            df = self.get_historical_data(symbol)
            if len(df) >= 2:
                prev_close = float(df['close'].iloc[-2])
                curr_price = float(df['close'].iloc[-1])
                return ((curr_price - prev_close) / prev_close) * 100
        except Exception:
            pass
        return 0.0

    def has_earnings_risk(self, symbol: str) -> bool:
        """Retorna True si el símbolo tiene earnings hoy o mañana."""
        earnings = self._get_earnings_today_and_tomorrow()
        if symbol in earnings:
            self.logger.warning(f"[EARNINGS GUARD] [WARN] {symbol} tiene reporte en <48h. Entrada bloqueada.")
            return True
        return False

    # ─── SECTOR HEALTH CHECK (SOXX) ───────────────────────────────────────────

    def is_sector_healthy(self) -> bool:
        """
        Verifica si el mercado general (QQQ) o sector tech (SOXX) están bajistas.
        Si SOXX cae > 3% o QQQ cae > 1.5% en el día → retorna False (Activa Rotación de Sector).
        """
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=[_SOXX_SYMBOL, _QQQ_SYMBOL])
            quote = self.data_client.get_stock_latest_quote(req)
            soxx_quote = quote.get(_SOXX_SYMBOL)
            qqq_quote = quote.get(_QQQ_SYMBOL)

            if not soxx_quote or not qqq_quote:
                self.logger.warning("[SECTOR] No se pudo obtener SOXX/QQQ. Asumiendo mercado sano.")
                return True

            # Comparar con el cierre anterior usando barras diarias
            bars_req = StockBarsRequest(
                symbol_or_symbols=[_SOXX_SYMBOL, _QQQ_SYMBOL],
                timeframe=TimeFrame.Day,
                start=datetime.now(_ET_TZ) - timedelta(days=3)
            )
            bars = self.data_client.get_stock_bars(bars_req)
            
            # Chequeo SOXX
            if not bars.df.empty and _SOXX_SYMBOL in bars.df.index.levels[0]:
                soxx_bars = bars.df.xs(_SOXX_SYMBOL, level='symbol')
                if len(soxx_bars) >= 2:
                    prev_close = float(soxx_bars['close'].iloc[-2])
                    current_price = float(soxx_quote.ask_price or soxx_quote.bid_price)
                    daily_change_pct = ((current_price - prev_close) / prev_close) * 100
                    if daily_change_pct <= _SECTOR_BEAR_THRESHOLD:
                        self.logger.warning(f"[SECTOR GUARD] [BEAR] SOXX cayó {daily_change_pct:.2f}% hoy. Activando ROTACIÓN DE SECTOR.")
                        self.notifier.send_critical_alert(f"SOXX cayó {daily_change_pct:.2f}% hoy.\n<b>Activando Rotación a ETFs Refugio ({', '.join(_SANCTUARY_SYMBOLS)}).</b>")
                        return False
                    self.logger.info(f"[SECTOR] [OK] SOXX: {daily_change_pct:+.2f}%")

            # Chequeo QQQ
            if not bars.df.empty and _QQQ_SYMBOL in bars.df.index.levels[0]:
                qqq_bars = bars.df.xs(_QQQ_SYMBOL, level='symbol')
                if len(qqq_bars) >= 2:
                    prev_close = float(qqq_bars['close'].iloc[-2])
                    current_price = float(qqq_quote.ask_price or qqq_quote.bid_price)
                    daily_change_pct = ((current_price - prev_close) / prev_close) * 100
                    if daily_change_pct <= _MARKET_BEAR_THRESHOLD:
                        self.logger.warning(f"[MARKET GUARD] [BEAR] QQQ cayó {daily_change_pct:.2f}% hoy. Activando ROTACIÓN DE SECTOR.")
                        self.notifier.send_critical_alert(f"QQQ cayó {daily_change_pct:.2f}% hoy.\n<b>Activando Rotación a ETFs Refugio ({', '.join(_SANCTUARY_SYMBOLS)}).</b>")
                        return False
                    self.logger.info(f"[MARKET] [OK] QQQ: {daily_change_pct:+.2f}%")

            return True

        except Exception as e:
            self.logger.warning(f"[SECTOR] Error verificando SOXX: {e}. Asumiendo OK.")
            return True

    # ─── POSITION CACHE (for broker-side close detection) ────────────────────

    def _load_positions_cache(self) -> dict:
        """Load position snapshot from disk."""
        try:
            if os.path.exists(self._positions_cache_file):
                with open(self._positions_cache_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_positions_cache(self, snapshot: dict):
        """Persist current position snapshot to disk."""
        try:
            with open(self._positions_cache_file, 'w') as f:
                json.dump(snapshot, f)
        except Exception as e:
            self.logger.error(f"[PosCache] Error guardando cache: {e}")

    def _build_positions_snapshot(self) -> dict:
        """
        Queries Alpaca for all open positions and returns a dict:
        { SYMBOL: {"qty": float, "avg_entry": float, "current_price": float, "pnl_usd": float} }
        """
        try:
            positions = self.trading_client.get_all_positions()
            snapshot = {}
            for pos in positions:
                snapshot[pos.symbol] = {
                    "qty": float(pos.qty),
                    "avg_entry": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "pnl_usd": float(pos.unrealized_pl)
                }
            return snapshot
        except Exception as e:
            self.logger.warning(f"[PosCache] Error consultando posiciones: {e}")
            return {}

    def _detect_and_report_closures(self):
        """
        Compares current open positions against the previous cycle's cache.
        If a position that was open is now gone → it was closed by the broker
        (OCO Take Profit, Stop Loss, or Trailing Stop hit).
        Sends a Telegram P&L notification for each closed position.
        """
        current_snapshot = self._build_positions_snapshot()
        prev_cache = self._positions_cache

        # Find positions that existed before but are now gone
        closed_symbols = set(prev_cache.keys()) - set(current_snapshot.keys())

        for symbol in closed_symbols:
            prev = prev_cache[symbol]
            avg_entry = prev.get("avg_entry", 0.0)
            qty = prev.get("qty", 0.0)
            last_price = prev.get("current_price", avg_entry)  # last known price
            pnl_usd = prev.get("pnl_usd", 0.0)
            side = "BUY" if qty > 0 else "SELL"

            self.logger.info(
                f"[PosCache] 📤 Posición cerrada detectada: {symbol} | "
                f"Entrada: {avg_entry} | Última: {last_price} | PnL: ${pnl_usd:+.2f}"
            )
            self.notifier.send_trade_close(
                symbol=symbol,
                side=side,
                entry_price=avg_entry,
                exit_price=last_price,
                qty=qty,
                pnl_usd=pnl_usd
            )

        # Update cache with the current snapshot
        self._positions_cache = current_snapshot
        self._save_positions_cache(current_snapshot)

    # ─── ORDER QUEUE ──────────────────────────────────────────────────────────

    def _load_queue(self):
        """Load persisted order queue from disk (survives bot restarts)."""
        try:
            if os.path.exists(self._queue_file):
                with open(self._queue_file, 'r') as f:
                    q = json.load(f)
                    if q:
                        self.logger.info(f"📂 Cargadas {len(q)} órdenes pendientes del disco.")
                    return q
        except Exception:
            pass
        return []

    def _save_queue(self):
        """Persist order queue to disk so it survives server restarts."""
        try:
            with open(self._queue_file, 'w') as f:
                json.dump(self.order_queue, f)
        except Exception as e:
            self.logger.error(f"[Queue] Error guardando cola: {e}")

    def _get_notional_per_trade(self) -> float:
        """
        Calcula el monto en USD por trade basado en el buying power disponible.
        Usa el mínimo entre el cap configurado y 1/15 del buying power.
        Garantiza órdenes fraccionadas correctas para acciones de alto precio.
        """
        try:
            account = self.trading_client.get_account()
            buying_power = float(account.buying_power)
            # 1/15 del capital disponible, con un tope de CAPITAL_PER_TRADE_USD
            notional_val = float(min(buying_power / len(self.watchlist), float(self._capital_per_trade)))
            notional_val = float(max(notional_val, 1.0))  # Mínimo $1 para acciones fraccionadas
            self.logger.info(f"[Sizing] Buying Power: ${buying_power:.2f} → ${notional_val:.2f} por trade")
            return float(round(float(notional_val), 2))
        except Exception as e:
            self.logger.warning(f"[Sizing] Error calculando notional: {e}. Usando ${self._capital_per_trade}")
            return self._capital_per_trade

    def get_historical_data(self, symbol):
        """Obtiene velas recientes para análisis técnico"""
        start_time = datetime.now() - timedelta(days=5)
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_time
        )
        bars = self.data_client.get_stock_bars(request_params)
        return bars.df

    def is_market_open(self):
        """
        Verifica el estado del mercado.

        ✅ FIX: Hora de ejecución cambiada de 9:29 AM a 10:00 AM (post-volatilidad).
        El rango 9:30-10:00 AM es el "Morning Shakeout" — ruido de apertura que
        genera falsas señales. Esperar hasta las 10:00 AM da una tendencia más real.

        Nocturno / Pre-Mercado: Solo Análisis y encolado.
        10:00 AM trigger: Ejecución de cola (re-validando señales).
        10:00 AM - 4:00 PM: Live Trading.
        """
        now = datetime.now(_ET_TZ)
        current_minutes = now.hour * 60 + now.minute

        if now.weekday() >= 5:
            return False, "OFFLINE", "Fin de semana"

        # ✅ FIX: Trigger ahora es 10:00 AM (minutos 600) no 9:29 AM (569)
        # Esto evita el "Morning Shakeout" (9:30-10:00 AM volatilidad inicial)
        if current_minutes == 600:  # 10:00 AM exacto
            return True, "TRIGGER", "Apertura Post-Shakeout (10:00 AM)"

        if current_minutes < 570:   # Antes de 9:30 AM
            return True, "ANALYZE_ONLY", "Análisis Nocturno/Pre-Mercado"

        if 570 <= current_minutes < 600:  # 9:30 AM - 9:59 AM
            return True, "ANALYZE_ONLY", "Morning Shakeout (esperar hasta 10:00 AM)"

        if current_minutes > 960:   # Después de 4:00 PM
            return True, "ANALYZE_ONLY", "Post-Mercado (Análisis)"

        return True, "LIVE", "Mercado Abierto (10:00 AM - 4:00 PM)"

    def scan_market(self):
        """Escanea 24/7 con todos los filtros de seguridad activados."""
        
        # ─── PANIC SWITCH CHECK (Integrado con Telegram Bot) ───────────────
        panic_lock_path = ".panic_lock"
        if os.path.exists(panic_lock_path):
            self.logger.warning("🛑 [PANIC SWITCH ACTIVO] El scanner está bloqueado por orden del usuario (.panic_lock). Use /resume en Telegram para restaurar.")
            return

        is_active, session_type, reason = self.is_market_open()
        if not is_active:
            self.logger.debug(f"🌖 {reason}. Sentinel en reposo.")
            return

        # ─── DETECT BROKER-SIDE CLOSURES (OCO/SL/TP hit) ─────────────────────
        # Must run each cycle to catch automatic closes by Alpaca
        self._detect_and_report_closures()

        if session_type == "TRIGGER":
            self.execute_queue()
            return

        self.logger.info(f"🔍 Escaneo ({session_type}): {time.strftime('%H:%M:%S')}")

        # ─── SECTOR HEALTH CHECK (solo en horario de mercado) ─────────────────
        # Determine which list of stocks to trade today based on macro health
        active_watchlist = self.watchlist
        is_healthy = True
        
        if session_type == "LIVE":
            if not self.is_sector_healthy():
                self.logger.info(f"🔴 Mercado bajista. Rotando a activos refugio: {_SANCTUARY_SYMBOLS}")
                active_watchlist = _SANCTUARY_SYMBOLS
                is_healthy = False

        # ─── EARNINGS CALENDAR (cache compartido para todos los símbolos) ───
        earnings_risk_set = self._get_earnings_today_and_tomorrow()

        # ─── MAESTRO LOGIC: Sector Health & Correlation Context ──────────────
        sector_change = self._get_daily_change_pct(_SOXX_SYMBOL)
        market_change = self._get_daily_change_pct(_QQQ_SYMBOL)
        
        # V2: Calcular Fuerza Relativa del Sector (SOXX vs SPY)
        soxx_df = self.get_historical_data(_SOXX_SYMBOL)
        spy_df = self.get_historical_data(_SPY_SYMBOL)
        strength_score, strength_label = self.cerebro.get_sector_strength(soxx_df, spy_df)
        
        # V2: Detectar Sesgo de Líderes (TSM, ASML)
        tsm_change = self._get_daily_change_pct("TSM")
        asml_change = self._get_daily_change_pct("ASML")
        leaders_bias = "NEUTRAL"
        if tsm_change > 0.5 and asml_change > 0.5:
            leaders_bias = "BULLISH"
        elif tsm_change < -0.5 and asml_change < -0.5:
            leaders_bias = "BEARISH"
            
        sector_context = {
            'strength_score': strength_score,
            'strength_label': strength_label,
            'leaders_bias': leaders_bias
        }
        
        self.logger.info(f"📊 CONTEXTO: SOXX vs SPY: {strength_score:+.2f}% ({strength_label}) | Bias Líderes: {leaders_bias}")

        if sector_change <= _SECTOR_BEAR_THRESHOLD or market_change <= _MARKET_BEAR_THRESHOLD:
            if session_type == "LIVE":
                self.logger.info(f"🔴 Mercado bajista ({sector_change:+.2f}%). Rotando a activos refugio.")
                active_watchlist = _SANCTUARY_SYMBOLS
                is_healthy = False

        # 2. Analizar la lista activa (Tech Watchlist o Sanctuary ETFs)
        for symbol in active_watchlist:
            try:
                df = self.get_historical_data(symbol)
                if df.empty:
                    self.logger.warning(f"⚠️ No hay datos para {symbol}. Saltando...")
                    continue
                current_price = float(df['close'].iloc[-1])
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol, sector_context)
                
                if signal:
                    # ✅ MAESTRO CALCULATION: Relative Strength & Whale Bypass
                    stock_change = self._get_daily_change_pct(symbol)
                    current_volume = df['volume'].iloc[-1]
                    avg_volume = df['volume'].tail(20).mean()
                    whale_factor = current_volume / avg_volume if avg_volume > 0 else 1.0
                    
                    is_massive_whale = whale_factor >= 3.0
                    is_stronger_than_sector = stock_change > sector_change + 0.5 # 0.5% de ventaja
                    
                    # El Veto Macro se levanta si la acción es "Rebelde" o hay "Ballena Masiva"
                    has_relative_strength = (signal == "BUY" and is_stronger_than_sector)
                    bypass_applied = is_massive_whale or has_relative_strength
                    
                    if not is_healthy and not bypass_applied and symbol not in _SANCTUARY_SYMBOLS:
                        self.logger.debug(f"🛡️ {symbol} vetado por salud de sector ({sector_change:+.2f}%) y falta de fuerza relativa.")
                        continue
                        
                    self.logger.info(f"💎 {symbol}: ${current_price:.2f} | {signal_reason}")
                    if bypass_applied and not is_healthy:
                        msg = "🐳 MASSIVE WHALE" if is_massive_whale else "💪 RELATIVE STRENGTH (Rebel Buy)"
                        self.logger.info(f"🔥 BYPASS MAESTRO: {msg} detectado en {symbol}.")

                # ─── MANTENIMIENTO DE POSICIONES ACTIVAS (ESCUDO OCO DÍA 2) ───
                if session_type == "LIVE" and self.executor.has_open_position(symbol):
                    if self.is_pdt_safe_to_sell(symbol):
                        if not self.executor.has_pending_orders(symbol):
                            self.logger.info(f"[SHIELD] Posición {symbol} en Día 2 sin escudo. Activando OCO.")
                            sl_price = float(round(float(current_price) * 0.98, 2))
                            tp_price = float(round(float(current_price) * 1.05, 2))
                            if self.autonomous_mode:
                                self.executor.place_oco_shield(symbol, tp_price=tp_price, sl_price=sl_price)
                                self.logger.info(f"[OCO] Escudo Día 2 activado: {symbol} | TP:{tp_price} | SL:{sl_price}")
                    else:
                        self.logger.info(f"[TIME] {symbol}: Posición en Día 1. Reteniendo Brackets por regla PDT.")

                # USER OVERRIDE: NO SHORT SELLING
                if signal == "SELL":
                    if not self.executor.has_open_position(symbol):
                        self.logger.debug(f"🛑 [NO SHORTS] Señal SHORT bloqueada para {symbol}. Solo operamos LONG.")
                        signal = None

                if not signal:
                    continue  # No valid signal — skip order phase for this symbol

                # ─── PDT CHECK para ventas LIVE ─────────────────────────────
                if signal == "SELL" and not self.is_pdt_safe_to_sell(symbol):
                    self.logger.info(f"🛡️ [PDT GUARD] Ignorando señal de VENTA para {symbol} por regla PDT.")
                    continue

                # ─── PDT HYBRID SHIELD ─────────────────────────────────────
                # Enviamos la orden "Nuda" (sin bracket) el Día 1 para evitar
                # cierres del broker que violen la regla PDT.
                sl_price = None
                tp_price = None
                side = OrderSide.BUY if signal == "BUY" else OrderSide.SELL
                notional = self._get_notional_per_trade()

                if session_type == "LIVE":
                    if self.autonomous_mode:
                        if side == OrderSide.SELL:
                            self.logger.info(f"Liquidando posición completa de {symbol}...")
                            try:
                                result = self.executor.client.close_position(symbol)
                            except Exception as e:
                                self.logger.error(f"Error cerrando posición {symbol}: {e}")
                                result = None
                        else:
                            result = self.executor.place_safe_order(
                                symbol, qty=None, notional=notional,
                                side=side, tp_price=tp_price, sl_price=sl_price
                            )
                        if result:
                            # ✅ ENTRY NOTIFICATION — the main Telegram alert
                            self.notifier.send_trade_open(
                                symbol=symbol,
                                side=signal,
                                price=current_price,
                                notional=notional,
                                reason=(
                                    f"{'🔥 MAESTRO BYPASS — ' if bypass_applied else ''}"
                                    f"{signal_reason}"
                                )
                            )
                            # Register purchase for transparency & PDT
                            if signal == "BUY":
                                sl = float(round(current_price * 0.98, 2))
                                tp = float(round(current_price * 1.05, 2))
                                self.record_purchase(symbol, entry_price=current_price, tp=tp, sl=sl)
                    else:
                        # Manual mode: notify user that action is needed
                        self.notifier.send_trade_open(
                            symbol=symbol,
                            side=signal,
                            price=current_price,
                            notional=notional,
                            reason=f"⚠️ MODO MANUAL — Confirmar en Alpaca. {signal_reason}"
                        )
                else:
                    # Nocturno: encolar en silencio (solo log)
                    self.logger.info(f"[Queue] Señal nocturna encolada: {signal} {symbol}")
                    self.order_queue.append({
                        "symbol": symbol,
                        "side": side.value,
                        "tp": tp_price,
                        "sl": sl_price,
                        "notional": notional,
                        "has_earnings_risk": symbol in earnings_risk_set
                    })
                    self._save_queue()

            except Exception as e:
                self.logger.error(f"❌ Error analizando {symbol}: {e}")

    def execute_queue(self):
        """
        Ejecuta la cola a las 10:00 AM re-validando señales y aplicando todos los
        filtros de seguridad: PDT, Earnings, SOXX sector health.
        """
        if not self.order_queue:
            return

        # ─── SECTOR HEALTH CHECK antes de ejecutar toda la cola ──────────────
        active_watchlist = self.watchlist
        if not self.is_sector_healthy():
            self.logger.warning(f"[Queue] SOXX bear market. Rotando ejecución a activos refugio: {_SANCTUARY_SYMBOLS}")
            # Solo permitiremos procesar órdenes nocturnas que pertenezcan a los activos refugio,
            # (aunque rara vez se encolarán si el refugio saltó de noche, nos protege de comprar tech hoy).
            active_watchlist = _SANCTUARY_SYMBOLS

        from alpaca.trading.enums import OrderSide
        total = len(self.order_queue)
        self.logger.info(f"🔥 10:00 AM! Re-validando {total} órdenes nocturnas...")

        # Refrescar la lista de earnings al momento de ejecutar
        earnings_risk_set = self._get_earnings_today_and_tomorrow()

        executed = 0
        for item in self.order_queue:
            symbol = item.get("symbol", "?")
            try:
                # Si el mercado está mal, solo procesar si el símbolo es un activo refugio
                if symbol not in active_watchlist:
                    self.logger.warning(f"[Queue] {symbol} no forma parte de la Watchlist Activa Hoy (Rotación de Sector). Omitiendo.")
                    continue

                # ─── EARNINGS RE-CHECK al ejecutar ──────────────────────────
                if item.get("side") == "buy" and symbol in earnings_risk_set:
                    self.logger.warning(f"[EARNINGS] {symbol}: reporte detectado. Orden nocturna cancelada.")
                    continue  # Silently skip — no need to spam Telegram

                # Re-validate: is the signal still valid at 10:00 AM?
                df = self.get_historical_data(symbol)
                current_price = df['close'].iloc[-1]
                # En Trigger también pasamos contexto pero es menos relevante que en LIVE
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol, sector_context=None)

                # USER OVERRIDE: NO SHORT SELLING
                if signal == "SELL":
                    if not self.executor.has_open_position(symbol):
                        signal = None
                        self.logger.debug(f"[Queue] 🛑 Señal SHORT de 10AM bloqueada para {symbol}.")

                original_side_str = item["side"]
                expected_signal = "BUY" if original_side_str == "buy" else "SELL"

                if signal != expected_signal:
                    self.logger.warning(f"[Queue] {symbol}: señal obsoleta, omitida ({expected_signal} → {signal or 'WAIT'}).")
                    continue  # Silent skip — stale signals are not user-relevant

                # ─── PDT CHECK para ventas en cola ──────────────────────────
                if original_side_str == "sell" and not self.is_pdt_safe_to_sell(symbol):
                    continue  # Bloqueado por PDT

                # ─── EXISTING POSITION GUARD ─────────────────────────────────
                if expected_signal == "BUY" and (self.executor.has_open_position(symbol) or self.executor.has_pending_orders(symbol)):
                    self.logger.info(f"[Queue] 🛡️ Posición ya abierta en {symbol}. Omitiendo nueva compra.")
                    continue

                # ─── PDT HYBRID SHIELD ─────────────────────────────────────
                sl_price = None
                tp_price = None
                side = OrderSide.BUY if expected_signal == "BUY" else OrderSide.SELL

                notional = item.get("notional", self._capital_per_trade)
                if side == OrderSide.SELL:
                    self.logger.info(f"[Queue] Liquidando posición completa de {symbol}...")
                    try:
                        result = self.executor.client.close_position(symbol)
                    except Exception as e:
                        self.logger.error(f"Error cerrando posición {symbol}: {e}")
                        result = None
                else:
                    result = self.executor.place_safe_order(
                        symbol, qty=None, notional=notional,
                        side=side, tp_price=tp_price, sl_price=sl_price
                    )

                if result:
                    # ✅ ENTRY NOTIFICATION for queue execution at 10 AM
                    current_price_f = float(df['close'].iloc[-1]) if df is not None and not df.empty else 0.0
                    self.notifier.send_trade_open(
                        symbol=symbol,
                        side=expected_signal,
                        price=current_price_f,
                        notional=notional,
                        reason=f"Ejecución 10:00 AM — señal nocturna confirmada. {signal_reason}"
                    )
                    # Registrar compra para PDT & Transparencia
                    if expected_signal == "BUY":
                        sl_f = float(round(current_price_f * 0.98, 2))
                        tp_f = float(round(current_price_f * 1.05, 2))
                        self.record_purchase(symbol, entry_price=current_price_f, tp=tp_f, sl=sl_f)

                executed += 1
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Error ejecutando {symbol}: {e}")

        self.order_queue = []
        self._save_queue()
        # Log summary to file only — no Telegram noise
        self.logger.info(f"[Queue] 10:00 AM ejecutada: {executed}/{total} órdenes confirmadas.")

    def run(self):
        """Bucle principal de vigilancia"""
        try:
            while True:
                self.scan_market()
                self.logger.info("-" * 30)
                time.sleep(60)  # Escaneo por minuto
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Vigilancia detenida por el usuario.")


if __name__ == "__main__":
    watcher = NivoStockWatcher()
    watcher.run()

