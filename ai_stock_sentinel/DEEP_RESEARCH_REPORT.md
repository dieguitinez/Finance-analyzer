# 🔍 Deep Research: Monopolios de Hardware IA (2026)

Este reporte sintetiza la investigación sobre la cadena de valor de la Inteligencia Artificial y las mejores plataformas para trading algorítmico en el mercado de acciones.

---

## 1. El Trono de la IA: La Cadena de Suministro (Monopolios)
La IA no es solo software; es hardware físico. Estas son las 15 empresas que controlan los "ladrillos" de la revolución:

| Categoría | Empresa (Ticker) | Cuota de Mercado / Rol Crítico |
| :--- | :--- | :--- |
| **Cerebros (GPU)** | **NVIDIA (NVDA)** | 85-92% del mercado. Dueños del ecosistema CUDA. |
| **Fabricación** | **TSMC (TSM)** | 72% de la fundición global. Fabrican para todos (NVDA, AAPL). |
| **Litografía** | **ASML (ASML)** | Monopolio 100% en máquinas EUV. Sin ellos no hay chips de 3nm. |
| **Diseño IP** | **ARM (ARM)** | Arquitectura base de casi todos los diseños de chips modernos. |
| **Conectividad** | **Broadcom (AVGO)** | Líder en redes para centros de datos y chips personalizados. |
| **Memoria (HBM)** | **Micron (MU)** | Proveedor crítico de memoria HBM3E para los sistemas NVIDIA. |
| **Desafiante GPU** | **AMD (AMD)** | Único rival real de NVIDIA en aceleradores de IA. |
| **Software de Diseño** | **Synopsys (SNPS)** | Monopolio en herramientas EDA para diseñar los chips. |
| **Software de Diseño** | **Cadence (CDNS)** | El otro pilar fundamental del diseño electrónico. |
| **Equipamiento** | **Lam Research (LRCX)** | Esencial para el grabado de silicio en chips avanzados. |
| **Equipamiento** | **Applied Materials (AMAT)** | El mayor proveedor de máquinas para fábricas de chips. |
| **Control de Calidad** | **KLA (KLAC)** | Líder en metrología y detección de defectos en obleas. |
| **Infraestructura** | **Vertiv (VRT)** | Monopolio en enfriamiento y energía para racks de IA. |
| **Conectividad** | **Marvell (MRVL)** | Clave en interconexiones de fibra óptica para clusters de IA. |
| **Servidores** | **Supermicro (SMCI)** | Ensamblaje de racks de IA de alta densidad (Alta volatilidad). |

---

## 2. Plataformas de Trading (Bots): El "OANDA" de Acciones
He comparado las plataformas más amigables para desarrolladores:

### 🏆 Ganador: **Alpaca Markets**
- **Por qué**: Es lo más parecido a OANDA. Nació para ser usado por bots.
- **Ventajas**: API REST moderna, SDK de Python excelente, **Paper Trading** gratuito para probar estrategias sin dinero real, y **Zero Commissions** en acciones de EE.UU.
- **Veredicto**: Recomendado para arrancar con el Nivo AI Stock Sentinel.

### 🥈 Alternativa Profesional: **Interactive Brokers (IBKR)**
- **Por qué**: Es el estándar de la industria.
- **Ventajas**: Acceso global y robustez total. 
- **Desventajas**: La configuración del Bot es mucho más compleja y tediosa que Alpaca.

---

## 3. Sentimiento del Mercado 2026
- **Escasez de Memoria**: La memoria HBM está vendida por completo para todo 2026. Empresas como **Micron (MU)** tienen un poder de fijación de precios enorme.
- **Gaps de Apertura**: NVDA y TSM son propensos a saltos del 5-8% tras reportes de ganancias. Nuestro bot debe filtrar estos momentos para evitar entrar en el pico de la euforia.

---

## 🚀 Próximos Pasos
1. **Selección Final**: Confirmar si usamos Alpaca (Recomendado).
2. **Setup de API**: Crear cuenta de Paper Trading en Alpaca para obtener las `API_KEYS`.
3. **Draft del Sentinel**: Empezar el código del "Escaner de Monopolios" en la carpeta `ai_stock_sentinel/`.
