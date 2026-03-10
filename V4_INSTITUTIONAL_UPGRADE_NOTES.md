# Nivo Bot V4: Resumen de Actualizaciones Institucionales (Marzo 2026)

Este documento ha sido redactado con un enfoque **pedagógico y estructurado** ("estilo profesor") para que cualquier desarrollador humano o agente de Inteligencia Artificial que revise este repositorio en el futuro pueda entrar en contexto inmediatamente.

El objetivo principal de la **Actualización V4** fue escalar las capacidades de los bots de un nivel *"Retail"* (minorista guiado por indicadores básicos) a un nivel *"Institucional"* (fondos de cobertura guiados por macroeconomía, protección de capital extrema y gestión asimétrica del riesgo).

A continuación se detallan las mejoras implementadas en los dos motores principales: **Forex** y **Acciones**.

---

## 🌍 Parte 1: Nivo Forex Bot V4

El mercado de divisas es un juego de suma cero determinado por el flujo de capital global, donde el dólar estadounidense (USD) es el rey. Para el Bot de Forex, implementamos dos pilares críticos.

### 1.1. Filtro Macro Institucional (DXY Correlation)

**Archivo Modificado:** `vm_executor.py`

**El Problema:** El bot anterior podía identificar un hermoso patrón técnico ("Momentum Alcista") en pares como GBP/USD o AUD/USD y ejecutar compras. Sin embargo, si al mismo tiempo el Índice del Dólar Estadounidense (DXY) estaba en una fuerte tendencia alcista macro, esas compras de libras o dólares australianos estaban condenadas al fracaso, porque "no se puede pelear contra el dólar".

**La Solución (La Regla del Rey):** Se integró un chequeo condicional antes de cualquier ejecución que involucre al Dólar (ej. EUR/USD, USD/JPY).

- El bot consulta el estado de la **Media Móvil Exponencial de 50 periodos (EMA 50)** del activo virtual `USDOLLAR` (el DXY en OANDA).
- Si el DXY está alcista (Precio > EMA 50), el bot tiene **prohibido** ejecutar operaciones que impliquen vender o apostar contra el USD (ej. Long en EUR/USD o Short en USD/JPY).
- **Por qué funciona:** Al alinear las operaciones locales con el flujo monetario global, se eliminan las "trampas alcistas/bajistas" donde el análisis técnico miente debido a la presión macroeconómica externa.

### 1.2. Paridad de Volatilidad (Sizing Dinámico por ATR)

**Archivo Modificado:** `vm_executor.py` y `auto_execution.py`

**El Problema:** Operar con "Lotes Fijos" (ej. siempre comprar 0.01 lotes) es peligroso porque no todos los pares se mueven igual. Un lote en el CHF/JPY puede representar un riesgo de $5 USD si el par se mueve en tu contra, mientras que ese mismo lote en GBP/JPY puede representar un riesgo de $25 USD por su alta volatilidad.

**La Solución (Riesgo Constante en USD):**

- Se utiliza el **Rango Promedio Verdadero (ATR)** para medir la volatilidad histórica reciente del par.
- El usuario define un "Impacto Económico Tolerado" en su cuenta (ej. arriesgar exactamente `$20 USD` en el peor escenario).
- Una fórmula matemática calcula el tamaño exacto del lote (Position Sizing) dividiendo los `$20 USD` de riesgo objetivo entre la distancia monetaria que representa el ATR.
- **Por qué funciona:** Transforma una curva de capital caótica y llena de picos en una línea suave y estable. Ya no importa si el par es aburrido o explosivo; el dolor (Max Drawdown) siempre está pre-calculado y contenido.

---

## 🦅 Parte 2: Nivo Stock Sentinel V4

El mercado de acciones está fuertemente dictado por ciclos económicos, rotaciones institucionales y riesgos de reporte. Además, enfrentábamos una restricción de la cuenta vital: **No poseer el margen de $25,000 USD requerido para operar en corto (Short Selling).** Toda la estrategia debía diseñarse asumiendo un sesgo estrictamente de compra (*Long-Only*).

### 2.1. Escudo de Earnings Optimizado (Earnings Shield V2)

**Archivo Modificado:** `stock_watcher.py`

**El Problema:** Los reportes de ganancias corporativas (*Earnings Calls*) son una ruleta rusa. Si el bot compra una acción el lunes que reporta excelentes fundamentales, pero la empresa emite una proyección pesimista para el próximo año, la acción puede colapsar un 15% el martes ("Implied Volatility Crush"). La API gratuita anterior de Nasdaq a veces fallaba y el bot quedaba a ciegas frente a estos eventos.

**La Solución:**

- Se migró el motor de descubrimiento de calendario económico a la librería `yfinance`, que extrae la fecha de forma más robusta.
- El escudo escanea a 48 horas de distancia. Si hay un reporte inminente, se bloquea por completo la entrada a nuevas posiciones en ese símbolo, forzando al bot a buscar oportunidades en empresas cuya tormenta ya haya pasado.

### 2.2. Rotación a Activos Refugio (Sanctuary ETFs)

**Archivo Modificado:** `stock_watcher.py`

**El Problema:** Anteriormente, la función `is_sector_healthy()` ponía al bot en "Modo Retiro" (100% Cash) cuando detectaba caídas fuertes en el QQQ (Nasdaq general) o el SOXX (Semiconductores). Quedarse en efectivo protege el dinero, pero desaprovecha el capital dormido. Dado que **no podemos apostar en corto**, debíamos buscar ganancia alcista en medio del pánico.

**La Solución (La Ley de Conservación del Miedo):**

- Cuando el mercado tecnológico (QQQ/SOXX) se torna bajista, el bot apaga automáticamente el radar de la lista de vigilancia tecnológica principal.
- Instantánea y autónomamente, **rota la vigilancia** hacia dos instrumentos de refugio:
  - **$GLD (SPDR Gold Trust):** El oro es el refugio ancestral ante la inflación y el miedo bursátil, y tiende a subir cuando las acciones caen.
  - **$XLU (Utilities Sector ETF):** Agrupa empresas de servicios básicos regulados (agua, electricidad). Suben en pánico porque la gente siempre paga su recibo de luz, ofreciendo dividendos seguros y estabilidad.
- **Por qué funciona:** Mantiene el dinero trabajando y generando Alpha (rendimiento superio) capturando la mudanza institucional de "Dinero de Riesgo" a "Dinero Seguro".

### 2.3. Caza de Cisnes Negros (Mean Reversion - Contrarian Buy)

**Archivo Modificado:** `cerebral_engine.py`

**El Problema:** El motor original (`StockCerebralEngine`) solo perseguía rompimientos fuertes con la tendencia a favor (Momentum/Trend Following). Ignoraba ocasiones donde el mercado perdía la razón temporalmente.

**La Solución (El Principio de la Goma Elástica):**

- Si una empresa es sólida, pero de pronto sufre un castigo severo e irracional que hace que el precio baje más del `3%` de su promedio reciente (EMA-20), y los indicadores de sobreventa marcan un RSI `< 25` (Pánico extremo), la goma elástica está estirada al máximo.
- Si en ese foso de desesperación el bot detecta que comienza a entrar Volumen Masivo Institucional (una "Ballena" comenzando a acumular gangas), el bot emitirá la ansiada señal: `🩸 MEAN REVERSION (CONTRARIAN BUY)`.
- **Por qué funciona:** Permite aprovechar desplomes de empresas premium que el mercado sobrerreaccionó, brindando puntos de entrada con una relación riesgo-recompensa extremadamente ventajosa.

---

### Conclusión para el Futuro Lector

Como revisor de este código, ten presente que Nivo V4 no fue diseñado solo para generar alertas técnicas visuales. Está programado con la psicología para entender el contexto: "No importa cuán bueno sea el patrón del indicador, si el Macro y los fundamentales no están de nuestro lado, nos quedamos quietos o nos refugiamos".

> *"Los novatos buscan la entrada perfecta, los profesionales buscan el contexto perfecto".*
> — Nivo Bot Architecture, 2026.
