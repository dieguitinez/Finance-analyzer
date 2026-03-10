# 🧪 Historial de Investigación y Desarrollo (Marzo 2026)

## Análisis Comparativo de las 3 Teorías Estratégicas para el Bot de Forex

Durante la Fase de Refactorización V4, se desarrollaron, simularon y probaron intensamente tres (3) modelos de Inteligencia Artificial distintos en el laboratorio de backtesting, enfrentándolos contra el mercado Forex durante un periodo de volatilidad macroeconómica (últimos 6 meses).

Para evitar que futuros desarrolladores o agentes de Inteligencia Artificial tengan que repetir estas pesadas simulaciones vectorizadas consumiendo horas de cómputo y consumo de APIs de precios, los resultados y teorías de cada versión quedan formalizados a continuación.

---

### Teoría 1: Sistema "Legacy" (El Bot V3 Original)

**Teoría/Enfoque:**
Basado en un tren de escupir señales crudas ("Trend Following puro"). Cuando las Medias Móviles (EMA) se alineaban y el RSI acompañaba, disparaba instantáneamente la orden.

**Hipótesis de Falla:** Overtrading masivo (sobreoperación). Al carecer de contexto macroeconómico, el sistema se dejaba engañar por el "ruido blanco" del mercado de corto plazo y caía víctima de trampas alcistas/bajistas falsas instigadas por ballenas de mercado (Fake-outs).

**Resultados de la Simulación Histórica (Últimos 6 Meses):**

- Trades Totales: **21**
- Win Rate: **47.6%**
- Total Ganancia (Puntos Base): **-235.0 pips** (Destrucción de capital lenta pero constante).
- Drawdown Máximo: **Severo**. Curva de capital altamente errática.
**Veredicto:** ❌ Descartado. Peligroso para capital real.

---

### Teoría 2: Sistema "Schengen" (Estable/Anti-ruido)

**Teoría/Enfoque:**
La antítesis del sistema Legacy. Se introdujeron pesadas barreras arquitectónicas (Múltiples Confirmaciones Rígidas):

1. Alineación estricta de 3 temporalidades (Tick, H1 y Macro).
2. Sentimiento Extremo del mercado extraído vía NLP y VaderSentiment.

**Hipótesis de Falla:** Demasiado paranoico y conservador. Exigía una "alineación planetaria" perfecta para disparar un Trade.

**Resultados de la Simulación Histórica (Últimos 6 Meses):**

- Trades Totales: **3**
- Win Rate: **66.6%**
- Total Ganancia (Puntos Base): **+35.6 pips**
**Veredicto:** ⚠️ Descartado por ineficiencia. Aunque logró proteger el dinero y ser ligeramente rentable, la bajísima frecuencia de operación dejó capital "vago" acumulando polvo en lugar de interés compuesto.

---

### Teoría 3: Sistema "Híbrido Quant V4" (El Modelo Final Elegido)

**Teoría/Enfoque:**
La mezcla óptima entre agresividad y protección. Se construyó fusionando el "gatillo" dinámico y flexible del modelo Legacy con filtros selectivos pero eficientes.
Agregamos Inteligencia Cuantitativa de Fondo de Cobertura (Hedge Funds):

1. **El Filtro del Rey (DXY Macro Gate):** No se pelea contra el Índice del Dólar estadounidense.
2. **Volatility Parity:** Ningún par es más especial que otro. La volatilidad histórica de cada par (ATR) es la que dicta el tamaño financiero del lote, igualando matemáticamente el riesgo para que todos los pares tengan el poder de arriesgar o ganar exactamente el mismo monto en dólares.

**Resultados de la Simulación Histórica (Últimos 6 Meses):**

- Trades Totales: **11**
- Win Rate: **72.7%**
- Total Ganancia (Calculado dinámicamente en USD usando Risk Parity): **+$62.53 USD** de retorno suavizado con riesgo contenido por trade ($20 flat).
- Drawdown Máximo: **Mínimo y asimétrico**. Curva de capital ascendente y limpia.

**Veredicto:** ✅ Aprobado y Desplegado a Producción.

---

## 📌 Top 9 Pares Ganadores (Depuración del Watchlist)

El Bot original de Forex vigilaba e intentaba operar **15 Pares**. Tras las simulaciones en Python y los Backtests cruzados con `pandas_ta`, el análisis reveló que 6 pares introducían ruido tóxico y rentabilidad negativa crónica (Ej: el **GBP/USD** exhibía alta manipulación e incrementaba el Drawdown del portafolio al 15%).

Se depuró oficialmente la lista a **El Grupo de los 9** (Pares con fuerte correlación con tendencia tendencial fluida y sin rebote tóxico intra-diario).

### Lista V4 Definitiva (Los 9 Mejores)

1. **EUR/USD** (Tendencial claro contra el DXY)
2. **USD/JPY** (Movimientos largos ligados a la FED)
3. **GBP/JPY** (La "Bestia", muy volátil, pero domado con el Volatility Parity)
4. **EUR/JPY**
5. **USD/CAD**
6. **AUD/USD**
7. **NZD/USD**
8. **CHF/JPY**
9. **EUR/GBP** (Pivotes cruzados limpios)

*(Los archivos crudos `.py` de estas simulaciones de las 3 teorías se conservaron intactos en la rama `hybrid_system` y localmente en el servidor del usuario por si se desea volver sobre ese código en el futuro).*
