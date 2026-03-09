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

# Cargar configuración aislada
load_dotenv('ai_stock_sentinel/.env')

# ─── PDT GUARD CONSTANTS ─────────────────────────────────────────────────────
# Archivo persistente para rastrear fechas de compra por símbolo
_PDT_TRACKER_FILE = "/tmp/nivo_stock_pdt_tracker.json"

# ─── SECTOR HEALTH CONSTANTS ──────────────────────────────────────────────────
# SOXX = iShares Semiconductor ETF. QQQ = Nasdaq 100
_SOXX_SYMBOL         = "SOXX"
_QQQ_SYMBOL          = "QQQ"
_SECTOR_BEAR_THRESHOLD = -3.0   # Si SOXX baja más de 3% en el día → Cash mode
_MARKET_BEAR_THRESHOLD = -1.5   # Si QQQ baja más de 1.5% en el día → Cash mode

# ─── EARNINGS CALENDAR API ───────────────────────────────────────────────────
# API pública de Nasdaq (gratuita, sin key) para earnings próximos
_EARNINGS_API_URL = "https://api.nasdaq.com/api/calendar/earnings?date={date}"
_EARNINGS_CACHE_FILE = "/tmp/nivo_earnings_cache.json"


class NivoStockWatcher:
    def __init__(self):
        # 🛡️ Configuración de Logs (Rotación Automática para evitar llenar el disco)
        log_file = 'ai_stock_sentinel/sentinel.log'
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

        self.logger.info(f"🚀 Nivo AI Stock Sentinel iniciado. Modo paper: {self.is_paper}")
        self.logger.info(f"📡 Monitoreando {len(self.watchlist)} activos: {self.watchlist}")
        self.logger.info(f"🤖 Autónomo: {'SÍ' if self.autonomous_mode else 'NO (Solo Alertas)'}")
        self.logger.info(f"💰 Capital por trade: ${self._capital_per_trade}")

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

    def record_purchase(self, symbol: str):
        """Registra la fecha de hoy como fecha de compra para un símbolo."""
        today = date.today().isoformat()
        self._pdt_tracker[symbol] = today
        self._save_pdt_tracker()
        self.logger.info(f"[PDT] Compra registrada: {symbol} @ {today}")

    def is_pdt_safe_to_sell(self, symbol: str) -> bool:
        """
        Intelligent PDT Protection:
        1. Si se compró ayer o antes, es seguro vender (no gasta count).
        2. Si se compró HOY, es un Day Trade. Verificamos la API de Alpaca.
        3. Si Alpaca reporta < 3 day trades, PERMITIMOS la venta.
        4. Si reporta >= 3, BLOQUEAMOS para proteger la cuenta.
        """
        purchase_date_str = self._pdt_tracker.get(symbol)
        
        # Si no hay registro o no es de hoy, es una posición antigua (SAFE)
        if not purchase_date_str:
            return True
            
        purchase_date = date.fromisoformat(purchase_date_str)
        today = date.today()
        
        if purchase_date < today:
            return True  # Fue comprado ayer o antes, vender no cuenta como day trade

        # --- ES UN DAY TRADE (Comprado HOY) ---
        try:
            account = self.trading_client.get_account()
            dt_count = int(account.daytrade_count)
            
            if dt_count < 3:
                self.logger.info(
                    f"[PDT GUARD] ⚠️ TOKEN DAY TRADE USADO para {symbol}. "
                    f"Fueron consumidos {dt_count}/3."
                )
                # Opcional: Avisar por Telegram si se está usando un "token" de day trade
                self.notifier.send_critical_alert(
                    f"⚠️ <b>Token Day Trade Usado: {symbol}</b>\n"
                    f"Llevamos {dt_count}/3 day trades en los últimos 5 días."
                )
                return True
            else:
                self.logger.warning(
                    f"[PDT GUARD] ❌ VENTA BLOQUEADA para {symbol}: "
                    f"MÁXIMO PDT ALCANZADO ({dt_count}/3). "
                    f"La venta se pospone para mañana."
                )
                self.notifier.send_critical_alert(
                    f"❌ <b>Venta Bloqueada por Regla PDT: {symbol}</b>\n"
                    f"La cuenta ya tiene {dt_count}/3 day trades. Se retendrá hasta mañana."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"[PDT GUARD] Error consultando Alpaca API: {e}. Bloqueando por seguridad.")
            return False

    # ─── EARNINGS FILTER ──────────────────────────────────────────────────────

    def _get_earnings_today_and_tomorrow(self) -> set:
        """
        Descarga la lista de compañías con reporte de earnings HOY o MAÑANA.
        Usa caché para no consumir la API en cada ciclo (TTL: 6 horas).
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
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NivoBot/1.0)",
            "Accept": "application/json"
        }

        for delta_days in [0, 1]:  # Hoy y mañana
            check_date = (now + timedelta(days=delta_days)).strftime("%Y-%m-%d")
            try:
                url = _EARNINGS_API_URL.format(date=check_date)
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", {}).get("rows", [])
                    for row in rows:
                        sym = row.get("symbol", "").upper().strip()
                        if sym:
                            earnings_symbols.add(sym)
                else:
                    self.logger.warning(f"[EARNINGS] API retornó {resp.status_code} para {check_date}")
            except Exception as e:
                self.logger.warning(f"[EARNINGS] Error consultando earnings para {check_date}: {e}")

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
            self.logger.info(f"[EARNINGS] 📅 Reportes en las próximas 48h: {earnings_symbols & set(self.watchlist)}")

        return earnings_symbols

    def has_earnings_risk(self, symbol: str) -> bool:
        """Retorna True si el símbolo tiene earnings hoy o mañana."""
        earnings = self._get_earnings_today_and_tomorrow()
        if symbol in earnings:
            self.logger.warning(f"[EARNINGS GUARD] ⚠️ {symbol} tiene reporte en <48h. Entrada bloqueada.")
            return True
        return False

    # ─── SECTOR HEALTH CHECK (SOXX) ───────────────────────────────────────────

    def is_sector_healthy(self) -> bool:
        """
        Verifica si el mercado general (QQQ) o sector tech (SOXX) están bajistas.
        Si SOXX cae > 3% o QQQ cae > 1.5% en el día → modo Cash (no entrar).
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
                        self.logger.warning(
                            f"[SECTOR GUARD] 🔴 SOXX cayó {daily_change_pct:.2f}% hoy. Modo Cash activado."
                        )
                        self.notifier.send_critical_alert(
                            f"SOXX cayó {daily_change_pct:.2f}% hoy.\n<b>Modo Cash activado.</b> No se abrirán posiciones nuevas."
                        )
                        return False
                    self.logger.info(f"[SECTOR] ✅ SOXX: {daily_change_pct:+.2f}%")

            # Chequeo QQQ
            if not bars.df.empty and _QQQ_SYMBOL in bars.df.index.levels[0]:
                qqq_bars = bars.df.xs(_QQQ_SYMBOL, level='symbol')
                if len(qqq_bars) >= 2:
                    prev_close = float(qqq_bars['close'].iloc[-2])
                    current_price = float(qqq_quote.ask_price or qqq_quote.bid_price)
                    daily_change_pct = ((current_price - prev_close) / prev_close) * 100
                    if daily_change_pct <= _MARKET_BEAR_THRESHOLD:
                        self.logger.warning(
                            f"[MARKET GUARD] 🔴 QQQ cayó {daily_change_pct:.2f}% hoy. Modo Cash activado."
                        )
                        self.notifier.send_critical_alert(
                            f"QQQ cayó {daily_change_pct:.2f}% hoy.\n<b>Modo Cash activado.</b> No se abrirán posiciones nuevas."
                        )
                        return False
                    self.logger.info(f"[MARKET] ✅ QQQ: {daily_change_pct:+.2f}%")

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
            notional = min(buying_power / len(self.watchlist), self._capital_per_trade)
            notional = max(notional, 1.0)  # Mínimo $1 para acciones fraccionadas
            self.logger.info(f"[Sizing] Buying Power: ${buying_power:.2f} → ${notional:.2f} por trade")
            return round(notional, 2)
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
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        panic_lock_path = os.path.join(project_root, ".panic_lock")
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
        if session_type == "LIVE":
            if not self.is_sector_healthy():
                self.logger.info("🔴 Sector/Mercado bajista. Modo Cash — no se abren posiciones nuevas.")
                return

        # ─── EARNINGS CALENDAR (cache compartido para todos los símbolos) ───
        earnings_risk_set = self._get_earnings_today_and_tomorrow()

        # 1. Analizar primero al Líder (ASML) como Indicador Adelantado
        sector_conviction = False
        try:
            asml_df = self.get_historical_data("ASML")
            asml_signal, _ = self.cerebro.analyze_momentum(asml_df, "ASML")
            if asml_signal:
                sector_conviction = True
                self.logger.info("🏛️ ALTA CONVICCIÓN: ASML está liderando el sector hoy.")
        except Exception as e:
            self.logger.error(f"⚠️ Error analizando líder ASML: {e}")

        # 2. Analizar el resto de la Watchlist
        for symbol in self.watchlist:
            try:
                df = self.get_historical_data(symbol)
                if df.empty:
                    self.logger.warning(f"⚠️ No hay datos para {symbol}. Saltando...")
                    continue
                current_price = float(df['close'].iloc[-1])
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol)
                self.logger.info(f"💎 {symbol}: ${current_price:.2f} | {signal_reason}")

                # ─── MANTENIMIENTO DE POSICIONES ACTIVAS (ESCUDO OCO DÍA 2) ───
                if session_type == "LIVE" and self.executor.has_open_position(symbol):
                    if self.is_pdt_safe_to_sell(symbol):
                        if not self.executor.has_pending_orders(symbol):
                            self.logger.info(f"🛡️ Posición {symbol} en Día 2 sin escudo. Activando OCO.")
                            sl_price = round(current_price * 0.98, 2)
                            tp_price = round(current_price * 1.05, 2)
                            if self.autonomous_mode:
                                self.executor.place_oco_shield(symbol, tp_price=tp_price, sl_price=sl_price)
                                # OCO shield is automatic maintenance — no Telegram needed
                                self.logger.info(f"[OCO] Escudo Día 2 activado: {symbol} | TP:{tp_price} | SL:{sl_price}")
                    else:
                        self.logger.info(f"⏳ {symbol}: Posición en Día 1. Reteniendo Brackets por regla PDT.")

                if not signal:
                    continue

                side = OrderSide.BUY if signal == "BUY" else OrderSide.SELL

                # ─── EARNINGS GUARD ─────────────────────────────────────────
                if signal == "BUY" and symbol in earnings_risk_set:
                    self.logger.warning(f"[EARNINGS GUARD] {symbol} tiene reporte <48h. Entrada BLOQUEADA.")
                    continue

                # ─── PDT GUARD (solo para SELL) ──────────────────────────────
                if signal == "SELL" and not self.is_pdt_safe_to_sell(symbol):
                    continue  # Bloqueado — se compró hoy mismo

                # ─── EXISTING POSITION GUARD ─────────────────────────────────
                if self.executor.has_open_position(symbol) or self.executor.has_pending_orders(symbol):
                    if signal == "BUY":
                        self.logger.info(f"🛡️ Posición ya abierta en {symbol}. Omitiendo nueva compra.")
                    continue

                # ─── PDT HYBRID SHIELD ─────────────────────────────────────
                # Envíamos la orden "Nuda" (sin bracket) el Día 1 para evitar 
                # cierres del broker que violen la regla PDT.
                sl_price = None
                tp_price = None

                is_high_conviction = sector_conviction or symbol == "ASML"
                notional = self._get_notional_per_trade()

                if session_type == "LIVE":
                    if self.autonomous_mode:
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
                                    f"{'🏛️ SECTOR CONVICTION — ' if is_high_conviction else ''}"
                                    f"{signal_reason}"
                                )
                            )
                            # Register purchase for PDT protection
                            if signal == "BUY":
                                self.record_purchase(symbol)
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
        if not self.is_sector_healthy():
            # send_critical_alert already sent by is_sector_healthy()/is_sector_healthy()
            self.logger.warning("[Queue] Cola bloqueada por SOXX bear market.")
            return

        from alpaca.trading.enums import OrderSide
        total = len(self.order_queue)
        self.logger.info(f"🔥 10:00 AM! Re-validando {total} órdenes nocturnas...")

        # Refrescar la lista de earnings al momento de ejecutar
        earnings_risk_set = self._get_earnings_today_and_tomorrow()

        executed = 0
        for item in self.order_queue:
            symbol = item.get("symbol", "?")
            try:
                # ─── EARNINGS RE-CHECK al ejecutar ──────────────────────────
                if item.get("side") == "buy" and symbol in earnings_risk_set:
                    self.logger.warning(f"[EARNINGS] {symbol}: reporte detectado. Orden nocturna cancelada.")
                    continue  # Silently skip — no need to spam Telegram

                # Re-validate: is the signal still valid at 10:00 AM?
                df = self.get_historical_data(symbol)
                current_price = df['close'].iloc[-1]
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol)

                original_side_str = item["side"]
                expected_signal = "BUY" if original_side_str == "buy" else "SELL"

                if signal != expected_signal:
                    self.logger.warning(f"[Queue] {symbol}: señal obsoleta, omitida ({expected_signal} → {signal or 'WAIT'}).")
                    continue  # Silent skip — stale signals are not user-relevant

                # ─── PDT CHECK para ventas en cola ──────────────────────────
                if original_side_str == "sell" and not self.is_pdt_safe_to_sell(symbol):
                    continue  # Bloqueado por PDT

                # ─── EXISTING POSITION GUARD ─────────────────────────────────
                if self.executor.has_open_position(symbol) or self.executor.has_pending_orders(symbol):
                    if expected_signal == "BUY":
                        self.logger.info(f"[Queue] 🛡️ Posición ya abierta en {symbol}. Omitiendo nueva compra.")
                    continue

                # ─── PDT HYBRID SHIELD ─────────────────────────────────────
                sl_price = None
                tp_price = None
                side = OrderSide.BUY if expected_signal == "BUY" else OrderSide.SELL

                notional = item.get("notional", self._capital_per_trade)
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
                    # Registrar compra para PDT
                    if expected_signal == "BUY":
                        self.record_purchase(symbol)

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
