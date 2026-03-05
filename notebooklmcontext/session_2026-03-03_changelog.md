# Nivo FX Bot — Sesión 2026-03-03
## Documentación Técnica Completa
### Nivel: Ingeniería de Software / ML Systems

---

## 1. CONTEXTO Y ESTADO DEL SISTEMA AL INICIO DE LA SESIÓN

### 1.1 Arquitectura General del Bot

El **Nivo FX Bot** es un sistema de trading algorítmico institucional para OANDA FX, compuesto por:

```
nivo-sentinel.timer (cada ~1 min)
    └── vm_executor.py          ← Motor de análisis y ejecución
        ├── DataEngine           ← Fetchea velas OANDA H1 (500 candles)
        ├── NivoTradeBrain       ← Hemisferio Izquierdo: análisis técnico
        ├── NivoCortex           ← Hemisferio Derecho: HMM + LSTM
        ├── FundamentalEngine    ← Noticias RSS + VADER sentiment NLP
        ├── QuantumBridge        ← Síntesis matemática de señales
        ├── CapitalGuardian      ← Risk management
        └── NivoAutoTrader       ← Ejecución en OANDA

nivo-bot.service (continuamente)
    └── nivo_tg_bot.py          ← Bot de Telegram
        └── Comandos + Notificaciones
```

### 1.2 Problema Crítico Identificado Al Inicio

El bot llevaba días abriendo **exclusivamente posiciones SHORT (SELL)** — cero LONGs. Causa confirmada:

**El LSTM estaba usando pesos aleatorios** para 8 de los 15 pares monitoreados (los modelos `.pth` no existían aún). Con pesos aleatorios, la red neuronal producía probabilidades bull sistemáticamente por debajo del 50% (~34-36%), lo cual empujaba el `final_score` del QuantumBridge por debajo de 40 → señal SELL.

### 1.3 Pares Monitoreados (15 total)

```python
PAIRS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD",
    "USD_CHF", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY",
    "AUD_JPY", "NZD_JPY", "EUR_AUD", "EUR_CHF", "CHF_JPY"
]
```

---

## 2. LSTM — ENTRENAMIENTO COMPLETO

### 2.1 Arquitectura del Modelo

```python
# src/nivo_cortex.py — NivoLSTM
class NivoLSTM(nn.Module):
    input_size  = 5        # [open_r, high_r, low_r, close_r, vol_normalized]
    hidden_size = 64
    num_layers  = 2
    dropout     = 0.2
    output_size = 1        # Sigmoid → probabilidad alcista [0, 1]
```

**Input features** (en `predict_next_move()`):
```python
# últimas 60 velas H1
open_r   = open  / open.shift(1) - 1   # retorno relativo apertura
high_r   = high  / open - 1            # rango superior
low_r    = low   / open - 1            # rango inferior
close_r  = close / open - 1            # retorno de sesión
vol_n    = volume / volume.mean()      # volumen normalizado
```

### 2.2 Proceso de Entrenamiento

- **Script:** `scripts/train_lstm.py`
- **Datos:** `scripts/download_oanda_data.py` → CSVs H1 de OANDA (~12,400 velas por par = ~2 años)
- **Epochs:** 30 con early stopping (guarda el mejor val_loss)
- **Duración:** ~3-4 horas total en CPU (Intel laptop), 2 procesos paralelos

### 2.3 Resultados

| Par | Guardado | Best Val Loss | Accuracy |
|---|---|---|---|
| EUR_USD | 21:45 | 0.6923 | 52.1% |
| GBP_USD | 21:53 | ~0.692 | ~51% |
| USD_JPY | 22:01 | ~0.692 | ~51% |
| AUD_USD | 22:09 | 0.6923 | ~52% |
| USD_CAD | 22:17 | ~0.692 | ~51% |
| USD_CHF | 22:22 | ~0.692 | ~51% |
| NZD_USD | 22:27 | 0.6924 | ~51% |
| EUR_JPY | 22:32 | ~0.692 | ~51% |
| GBP_JPY | 22:37 | 0.6918 | ~52% |
| AUD_JPY | 22:41 | ~0.692 | ~51% |
| NZD_JPY | ~22:46 | 0.6924 | 51.6% |
| CHF_JPY | 22:51 | 0.6924 | 52.0% |
| EUR_GBP | 22:55 | 0.6917 | 51.8% |
| EUR_CHF | 23:00 | 0.6930 | 50.3% |
| EUR_AUD | 23:05 | 0.6913 | 53.9% |

**Nota académica:** Val loss ~0.69 es esperado para clasificación binaria FX de corto plazo. Los modelos no serán perfectamente predictivos (mercado eficiente), pero eliminan el sesgo aleatorio. Accuracy 48-54% es suficiente para sesgar marginalmente el timing de entradas junto con el resto de filtros del sistema.

### 2.4 Carga de Pesos

```python
# src/nivo_cortex.py — NivoLSTM.__init__()
weights_path = os.path.join(_script_dir, f"lstm_{pair_safe}.pth")
# pair_safe = pair.replace("/", "_")  ← crítico: EUR/USD → EUR_USD
if os.path.exists(weights_path):
    self.load_state_dict(torch.load(weights_path, map_location="cpu"))
    self.is_trained = True
```

**Error histórico que ya fue corregido:** El sistema usaba `pair.replace("/", "_")` para construir el nombre del archivo, pero al mismo tiempo guardaba como `lstm_{pair}` sin reemplazar. Fue corregido en una sesión anterior.

### 2.5 Verificación en Producción

```
[23:17:14] [NivoLSTM] ✅ Loaded trained weights for USD/JPY
[23:17:14] [RIGHT HEMISPHERE] LSTM Bull Probability: 51.7%
```
→ Antes de training (pesos aleatorios): ~34.9% → señal SELL permanente  
→ Después de training (pesos reales): 51.7% → neutro, refleja mercado real

---

## 3. TELEGRAM BOT — SISTEMA DE NOTIFICACIONES REDISEÑADO

### 3.1 Eliminación del Spam CORTEX VETO

**Problema:** `vm_executor.py` líneas ~178-189 (original) enviaba un mensaje Telegram cada vez que el HMM vetaba un trade.

**Frecuencia del problema:** Con 15 pares corriendo cada minuto, y el régimen HMM siendo `Calm Low Volatility` para la mayoría de pares, el VETO se disparaba ~10-12 veces por ciclo → spam masivo.

**Solución aplicada** (`vm_executor.py`):
```python
# ANTES (eliminado):
if is_vetoed:
    logger.info(f"🛑 CORTEX VETO: {veto_reason}")
    requests.post(telegram_url, json={"text": f"🛑 CORTEX VETO\n{veto_reason}\nPar: {pair}"})
    sys.exit(0)

# DESPUÉS:
if is_vetoed:
    logger.info(f"🛑 CORTEX VETO: {veto_reason} | No trade will be executed.")
    sys.exit(0)  # Solo log local, cero Telegram
```

### 3.2 Notificación de Entrada con Botón de Pánico

**Archivo:** `src/notifications.py` — método `trade_execution_report()`

**Filosofía de diseño:** El usuario quería mínima información en Telegram salvo lo esencial: entrada, salida, P&L. Cualquier detalle adicional debe consultarse con comandos.

```python
# Inline keyboard en cada confirmación de trade
reply_markup = {
    "inline_keyboard": [[
        {"text": "🛑 KILL SWITCH — Cerrar Todo", "callback_data": "/kill"}
    ]]
}
```

El mensaje HTML incluye: hora, par, dirección (LONG/SHORT), unidades, ID de transacción, link a OANDA.

### 3.3 Comando `/close` — Cierre Selectivo de Posiciones

**Problema motivador:** El botón global KILL SWITCH cierra TODAS las posiciones. El usuario quería granularidad para cerrar una posición específica sin afectar las demás.

**Implementación:**

1. `/close` → consulta OANDA por posiciones abiertas → construye inline keyboard dinámico:
   ```
   [📉 S EUR/USD  $-2.40]
   [📉 S GBP/USD  $+1.80]
   [📉 S NZD/JPY  $+5.10]
   [🚫 Cancelar          ]
   ```

2. El usuario toca → `callback_query` con `data = "close:EUR_USD"`

3. Bot llama `NivoAutoTrader.close_single_position("EUR_USD")` (nuevo método)

**Nuevo método en `src/auto_execution.py`:**
```python
def close_single_position(self, instrument: str) -> dict:
    # 1. Normaliza: EUR/USD → EUR_USD
    # 2. GET /positions/{instrument} → determina side (LONG o SHORT)
    # 3. PUT /positions/{instrument}/close
    # 4. Extrae PnL de shortOrderFillTransaction o longOrderFillTransaction
    # 5. Retorna {"status": "success", "pl": float}
```

### 3.4 Comando `/report [PAR]` — Diagnóstico Interno Completo

**Motivación:** El usuario necesitaba poder auditar la decisión del bot en cualquier par, especialmente en posiciones perdedoras, para verificar si el análisis fue correcto.

**Arquitectura de implementación:**

```
Usuario: /report (sin args)
→ Bot: muestra picker inline 3 columnas × 5 filas (15 pares)

Usuario: toca EUR/USD (callback_data = "report:EUR_USD")
→ Bot: handle_command("/report", ["EUR_USD"])
→ subprocess: python3 vm_executor.py --diagnostic (TRADING_PAIR=EUR_USD)
→ vm_executor: análisis completo → JSON → stdout
→ Bot: parsea JSON, formatea mensaje HTML
```

**Flag `--diagnostic` en `vm_executor.py`:**
```python
if args.diagnostic:
    # Corre: DataEngine → NivoTradeBrain → NivoCortex → FundamentalEngine → QuantumBridge
    # NO ejecuta trade, NO envía notificación
    # Output: JSON a stdout con todos los resultados intermedios
    print(json.dumps(_report))
    sys.exit(0)
```

**Output del reporte en Telegram:**
```
🔬 DIAGNÓSTICO — EUR/USD
🕐 2026-03-03 22:55  |  💲 1.04821
══════════════════════

🧠 HEMISFERIO IZQUIERDO (Técnico)
  Score: 🔴 38.4/100  |  Señal: SELL
  RSI: 42.3  |  MACD: Bearish

🤖 HEMISFERIO DERECHO (IA)
  HMM Régimen: Calm / Low Volatility
  LSTM Bull:   🔴 34.9%  [⚠️ Aleatorio]

📰 FUNDAMENTAL
  Sentiment: 46.2/100  |  Headlines: 8

⚛️ PUENTE CUÁNTICO
  Score Final: 🔴 31.8/100  |  Q-Mult: 0.8x
══════════════════════
📉 DECISIÓN: SELL
(BUY >60 | SELL <40 | WAIT en el medio)
```

**Badges LSTM:** `✅ Entrenado` vs `⚠️ Aleatorio` — crucial para detectar pares sin modelo.

### 3.5 Manejo de Callbacks (Botones Inline)

**Antes:** Bot solo procesaba mensajes de texto (`/comando`).

**Después:** `poll_updates()` procesa dos tipos de update:

```python
if "callback_query" in update:
    # 1. answerCallbackQuery (elimina spinner en el botón)
    # 2. Enruta por prefijo:
    #    - "/kill" → handle_command("/kill", [])
    #    - "close:EUR_USD" → close_single_position("EUR_USD")
    #    - "report:EUR_USD" → handle_command("/report", ["EUR_USD"])
    continue

if "message" in update:
    # Procesamiento normal de comandos de texto
```

---

## 4. FUNDAMENTAL ENGINE — AUDITORÍA

### 4.1 Implementación Real

**Archivo:** `src/data_engine.py` — `class FundamentalEngine`

```python
@staticmethod
def get_pair_sentiment(pair_name):
    analyzer = SentimentIntensityAnalyzer()  # VADER NLP
    symbol = DataEngine.get_symbol_map(pair_name)  # EUR/USD → EURUSD=X
    
    rss_urls = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US",
        "https://www.marketpulse.com/feed/"
    ]
    
    # Máx 20 headlines recientes
    # compound VADER: [-1, +1] → mapeado a [0, 100]
    final_score = (avg_compound + 1.0) * 50.0
    return news_items, final_score  # fallback: [], 50.0
```

**Nota:** Yahoo RSS tiene restricciones por símbolo. En la práctica, MarketPulse da cobertura más general de FX. El fallback a 50.0 (neutral) es robusto — el sistema siempre puede operar sin noticias.

### 4.2 Bug Crítico Encontrado y Corregido

En el modo `--diagnostic` (nuevo), se había escrito incorrectamente:
```python
# ❌ INCORRECTO (clase inexistente):
from src.nivo_cortex import FundamentalAnalyzer
fa = FundamentalAnalyzer()
fund_sentiment = fa.get_sentiment_score(pair)

# ✅ CORRECTO:
fund_items, fund_sentiment = FundamentalEngine.get_pair_sentiment(pair)
fund_headlines = len(fund_items)
```

### 4.3 Bug Adicional Corregido — HMM en Modo Diagnóstico

```python
# ❌ INCORRECTO (método inexistente):
hmm_regime_id = cortex.hmm.predict_regime(df)

# ✅ CORRECTO (método real que retorna tupla):
hmm_regime_id, hmm_label = cortex.hmm.detect_regime(df)
if hmm_regime_id == -1:
    hmm_regime_id, hmm_label = 0, "Calm / Low Volatility"
```

---

## 5. ANÁLISIS DEL SESGO SELL — INVESTIGACIÓN COMPLETA

### 5.1 Diagnóstico

El usuario observó que el bot solo abría SELLs desde hace días. Se investigó en tres niveles:

**Nivel 1 — Logs del servidor:**
```
EUR/USD → LSTM Bull Probability: 34.9%
GBP/USD → LSTM Bull Probability: 35.8%
```
Todas las probabilidades sistemáticamente por debajo del 50%.

**Nivel 2 — Código (`quantum_bridge.py`):**
```python
raw_signal = "BUY" if final_score > 60.0 else "SELL" if final_score < 40.0 else "WAIT"
```
Umbral simétrico (BUY>60, SELL<40) → no hay sesgo en el código.

**Nivel 3 — Causa raíz:**
Con pesos aleatorios, la distribución de salidas del LSTM no es simétrica alrededor del 50%. La inicialización aleatoria específica del servidor producía outputs consistentemente bajos → scores < 40 → SELL permanente.

**Causa secundaria potencial (mercado):** 
USD fuerte en marzo 2026 (políticas arancelarias) genuinamente favorece cortos en EUR, GBP, AUD vs USD. Parte del sesgo puede ser real del mercado.

### 5.2 Resolución

Completar entrenamiento LSTM. Resultado inmediato:
- USD/JPY: 51.7% (neutro vs 35% aleatorio)
- El bot retomará LONGs cuando el mercado lo justifique

---

## 6. DEPLOYMENT Y VERIFICACIÓN

### 6.1 Archivos Modificados Esta Sesión

| Archivo | Tipo de cambio |
|---|---|
| `quantum_engine/vm_executor.py` | Eliminó VETO spam + añadió `--diagnostic` mode |
| `quantum_engine/nivo_tg_bot.py` | Bot commands: `/close`, `/report` + callback_query handler |
| `src/notifications.py` | `trade_execution_report()` con inline KILL button + HTML format |
| `src/auto_execution.py` | Nuevo método `close_single_position(instrument)` |

### 6.2 Comandos de Deployment Usados

```bash
cd /home/diego/nivo_fx

# Backup previo
cp quantum_engine/vm_executor.py quantum_engine/vm_executor.py.bak
cp quantum_engine/nivo_tg_bot.py quantum_engine/nivo_tg_bot.py.bak
cp src/notifications.py src/notifications.py.bak
cp src/auto_execution.py src/auto_execution.py.bak

# Reinicio
sudo systemctl restart nivo-sentinel.timer nivo-bot.service
```

### 6.3 Log de Verificación

```
Mar 03 23:17:12 | NIVO BOT: [INFO]       | Nivo Telegram Bot started. Listening for commands...
Mar 03 23:17:14 | NIVO SENTINEL: [INFO]  | [NivoLSTM] ✅ Loaded trained weights for USD/JPY
Mar 03 23:17:14 | NIVO SENTINEL: [INFO]  | [RIGHT HEMISPHERE] LSTM Bull Probability: 51.7%
```

---

## 7. PENDIENTES — PRÓXIMA SESIÓN

### 7.1 🔴 ALTA PRIORIDAD: Auto-Seguimiento Independiente de Volatilidad M5

**Problema observado:** El bot a veces no hace "seguimiento automático" (step-trailing) de posiciones abiertas cuando la volatilidad M5 está baja. Esto significa que posiciones ganadoras pueden no asegurar ganancias.

**Archivos a modificar:** `quantum_engine/vm_executor.py`  
**Lógica actual:** El seguimiento se activa solo si expansión M5 > umbral.  
**Fix propuesto:** El step-trailing de posiciones ABIERTAS debe ser siempre activo, independientemente de la volatilidad.

### 7.2 🔴 ALTA PRIORIDAD: Stop Loss < Spread Fix

**Problema:** OANDA rechaza órdenes con error `STOP_LOSS_ON_FILL_LOSS` cuando el SL calculado está más cercano que el spread.

**Archivo a modificar:** `quantum_engine/risk_manager.py`  
**Fix propuesto:** Antes de enviar la orden, verificar que `(entry_price - sl_price)` sea al menos `spread * 1.5`. Si no, ampliar el SL o cancelar el trade.

### 7.3 🟡 MEDIA PRIORIDAD: Notificación de Cierre por Trailing Stop

**Problema:** Cuando OANDA cierra automáticamente una posición por trailing stop, el usuario no recibe notificación en Telegram. Solo se da cuenta al consultar `/status`.  
**Solución propuesta:** En el ciclo del sentinel, detectar si una posición que estaba abierta ya no aparece en `/openPositions` → enviar notificación con PnL realizado.

### 7.4 🟡 MEDIA PRIORIDAD: Dashboard Streamlit vinculado desde Telegram

**Petición del usuario:** Poder consultar el análisis también visualmente, no solo por comandos de texto.  
**Opciones:**
1. Comando `/dashboard` que envía el URL de Streamlit Cloud
2. Integrar `/report` también como widget visual en `app.py`
