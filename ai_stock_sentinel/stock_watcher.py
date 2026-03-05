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
# SOXX = iShares Semiconductor ETF. Si cae > este % en el día → no operar
_SOXX_SYMBOL         = "SOXX"
_SECTOR_BEAR_THRESHOLD = -3.0   # Si SOXX baja más de 3% en el día → Cash mode

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
        Retorna True solo si la posición fue comprada en un día ANTERIOR al de hoy.
        Esto previene day trades con cuentas < $25,000.
        """
        purchase_date_str = self._pdt_tracker.get(symbol)
        if not purchase_date_str:
            # No hay registro de compra → asumimos que fue en otro ciclo → safe
            return True
        purchase_date = date.fromisoformat(purchase_date_str)
        today = date.today()
        is_safe = purchase_date < today
        if not is_safe:
            self.logger.warning(
                f"[PDT GUARD] ❌ VENTA BLOQUEADA para {symbol}: "
                f"fue comprado hoy ({purchase_date_str}). "
                f"Solo se puede vender a partir de mañana."
            )
        return is_safe

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
        Verifica si el sector de semiconductores (SOXX) está en modo bajista.
        Si SOXX cae más de 3% en el día → modo Cash (no entrar).
        """
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=[_SOXX_SYMBOL])
            quote = self.data_client.get_stock_latest_quote(req)
            soxx_quote = quote.get(_SOXX_SYMBOL)

            if not soxx_quote:
                self.logger.warning("[SECTOR] No se pudo obtener SOXX. Asumiendo mercado sano.")
                return True

            # Comparar con el cierre anterior usando barras diarias
            bars_req = StockBarsRequest(
                symbol_or_symbols=[_SOXX_SYMBOL],
                timeframe=TimeFrame.Day,
                start=datetime.now(_ET_TZ) - timedelta(days=3)
            )
            bars = self.data_client.get_stock_bars(bars_req)
            soxx_bars = bars.df
            if soxx_bars.empty or len(soxx_bars) < 2:
                return True

            prev_close = float(soxx_bars['close'].iloc[-2])
            current_price = float(soxx_quote.ask_price or soxx_quote.bid_price)
            daily_change_pct = ((current_price - prev_close) / prev_close) * 100

            if daily_change_pct <= _SECTOR_BEAR_THRESHOLD:
                self.logger.warning(
                    f"[SECTOR GUARD] 🔴 SOXX cayó {daily_change_pct:.2f}% hoy. "
                    f"Umbral: {_SECTOR_BEAR_THRESHOLD}%. Modo Cash activado."
                )
                self.notifier.send_raw_message(
                    f"🔴 <b>ALERTA SECTOR:</b> SOXX cayó {daily_change_pct:.2f}% hoy.\n"
                    f"El Sentinel ha activado <b>Modo Cash</b>. No se abrirán posiciones."
                )
                return False

            self.logger.info(f"[SECTOR] ✅ SOXX: {daily_change_pct:+.2f}% — Mercado sano.")
            return True

        except Exception as e:
            self.logger.warning(f"[SECTOR] Error verificando SOXX: {e}. Asumiendo OK.")
            return True

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
        is_active, session_type, reason = self.is_market_open()
        if not is_active:
            print(f"🌖 {reason}. Sentinel en reposo.")
            return

        if session_type == "TRIGGER":
            self.execute_queue()
            return

        print(f"\n🔍 Escaneo ({session_type}): {time.strftime('%H:%M:%S')}")

        # ─── SECTOR HEALTH CHECK (solo en horario de mercado) ─────────────────
        if session_type == "LIVE":
            if not self.is_sector_healthy():
                print("🔴 Sector bajista. Modo Cash — no se abren posiciones nuevas.")
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
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol)
                current_price = df['close'].iloc[-1]

                print(f"💎 {symbol}: ${current_price:.2f} | {signal_reason}")

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
                if signal == "BUY" and self.executor.has_open_position(symbol):
                    self.logger.info(f"🛡️ Posición ya abierta en {symbol}. Omitiendo nueva compra.")
                    continue

                # Calcular Bracket (2% SL, 5% TP)
                if signal == "BUY":
                    sl_price = round(current_price * 0.98, 2)
                    tp_price = round(current_price * 1.05, 2)
                else:
                    sl_price = round(current_price * 1.02, 2)
                    tp_price = round(current_price * 0.95, 2)

                is_high_conviction = sector_conviction or symbol == "ASML"
                notional = self._get_notional_per_trade()

                if session_type == "LIVE":
                    icon = "🚀" if signal == "BUY" else "🔻"
                    msg = f"{icon} *Nivo Sentinel:* Señal {signal} en {symbol}\nMotivo: {signal_reason}"
                    if is_high_conviction:
                        msg = f"🏛️ *SECTOR CONVICTION ALERT*\n{msg}"
                    msg += f"\n🛡️ *Safety:* SL: {sl_price} | TP: {tp_price}"
                    msg += f"\n💰 *Notional:* ${notional}"

                    if self.autonomous_mode:
                        self.notifier.send_alert(f"{msg}\n✅ *Ejecutando orden fraccionada...*")
                        result = self.executor.place_safe_order(
                            symbol, qty=None, notional=notional,
                            side=side, tp_price=tp_price, sl_price=sl_price
                        )
                        # Registrar compra para protección PDT
                        if signal == "BUY" and result:
                            self.record_purchase(symbol)
                    else:
                        self.notifier.send_alert(f"{msg}\n⚠️ *Esperando validación (Modo Manual).*")
                else:
                    # Modo nocturno: encolar
                    print(f"⏳ SEÑAL NOCTURNA: Encolando {signal} para {symbol}")
                    self.order_queue.append({
                        "symbol": symbol,
                        "side": side.value,
                        "tp": tp_price,
                        "sl": sl_price,
                        "notional": notional,
                        "has_earnings_risk": symbol in earnings_risk_set
                    })
                    self._save_queue()
                    self.notifier.send_raw_message(
                        f"🌑 <b>Análisis Nocturno:</b> Señal <b>{signal}</b> en <b>{symbol}</b>. "
                        f"Encolada para apertura (10:00 AM)."
                    )

            except Exception as e:
                print(f"❌ Error analizando {symbol}: {e}")

    def execute_queue(self):
        """
        Ejecuta la cola a las 10:00 AM re-validando señales y aplicando todos los
        filtros de seguridad: PDT, Earnings, SOXX sector health.
        """
        if not self.order_queue:
            return

        # ─── SECTOR HEALTH CHECK antes de ejecutar toda la cola ──────────────
        if not self.is_sector_healthy():
            self.notifier.send_raw_message(
                "🔴 <b>Cola de apertura BLOQUEADA:</b> SOXX detecta mercado bajista. "
                "Esperando condiciones favorables."
            )
            return

        from alpaca.trading.enums import OrderSide
        total = len(self.order_queue)
        print(f"🔥 10:00 AM! Re-validando {total} órdenes nocturnas...")
        self.notifier.send_raw_message(
            f"🔥 <b>10:00 AM — Post-Shakeout!</b> Re-validando {total} órdenes nocturnas..."
        )

        # Refrescar la lista de earnings al momento de ejecutar
        earnings_risk_set = self._get_earnings_today_and_tomorrow()

        executed = 0
        for item in self.order_queue:
            symbol = item.get("symbol", "?")
            try:
                # ─── EARNINGS RE-CHECK al ejecutar ──────────────────────────
                if item.get("side") == "buy" and symbol in earnings_risk_set:
                    self.logger.warning(f"[EARNINGS] {symbol}: reporte detectado. Orden nocturna cancelada.")
                    self.notifier.send_raw_message(
                        f"⚠️ <b>{symbol}:</b> Tiene reporte de earnings. Orden cancelada por seguridad."
                    )
                    continue

                # Re-validate: is the signal still valid at 10:00 AM?
                df = self.get_historical_data(symbol)
                current_price = df['close'].iloc[-1]
                signal, signal_reason = self.cerebro.analyze_momentum(df, symbol)

                original_side_str = item["side"]
                expected_signal = "BUY" if original_side_str == "buy" else "SELL"

                if signal != expected_signal:
                    self.notifier.send_raw_message(
                        f"⚠️ <b>{symbol}:</b> Señal nocturna caducó "
                        f"({expected_signal} → {signal or 'WAIT'}). Orden cancelada."
                    )
                    self.logger.warning(f"[Queue] {symbol}: señal obsoleta, omitida.")
                    continue

                # ─── PDT CHECK para ventas en cola ──────────────────────────
                if original_side_str == "sell" and not self.is_pdt_safe_to_sell(symbol):
                    continue  # Bloqueado por PDT

                # ─── EXISTING POSITION GUARD ─────────────────────────────────
                if expected_signal == "BUY" and self.executor.has_open_position(symbol):
                    self.logger.info(f"[Queue] 🛡️ Posición ya abierta en {symbol}. Omitiendo nueva compra.")
                    continue

                # Recalcular SL/TP al precio de apertura real (10:00 AM)
                if expected_signal == "BUY":
                    sl_price = round(current_price * 0.98, 2)
                    tp_price = round(current_price * 1.05, 2)
                    side = OrderSide.BUY
                else:
                    sl_price = round(current_price * 1.02, 2)
                    tp_price = round(current_price * 0.95, 2)
                    side = OrderSide.SELL

                notional = item.get("notional", self._capital_per_trade)
                result = self.executor.place_safe_order(
                    symbol, qty=None, notional=notional,
                    side=side, tp_price=tp_price, sl_price=sl_price
                )

                # Registrar compra para PDT
                if expected_signal == "BUY" and result:
                    self.record_purchase(symbol)

                executed += 1
                time.sleep(1)
            except Exception as e:
                print(f"Error ejecutando {symbol}: {e}")

        self.order_queue = []
        self._save_queue()
        self.notifier.send_raw_message(
            f"✅ Apertura 10:00 AM ejecutada: {executed}/{total} órdenes confirmadas."
        )

    def run(self):
        """Bucle principal de vigilancia"""
        try:
            while True:
                self.scan_market()
                print("-" * 30)
                time.sleep(60)  # Escaneo por minuto
        except KeyboardInterrupt:
            print("\n🛑 Vigilancia detenida por el usuario.")


if __name__ == "__main__":
    watcher = NivoStockWatcher()
    watcher.run()
