# 🤖 Guía Estratégica: El Monopolio de la Inteligencia Artificial (Acciones)

Esta guía ha sido diseñada para transicionar tu mentalidad de **Forex Trader** (Divisas) a **Stock Trader** (Acciones), enfocándonos en el sector que está moviendo el mundo: **Semiconductores y Hardware de IA**.

---

## 1. El Triángulo del Poder: ¿Qué empresas operar?
No todas las empresas de IA son iguales. La clave está en los **Monopolios de Infraestructura**:

| Empresa | Ticket | Por qué es un "Monopolio" |
| :--- | :--- | :--- |
| **NVIDIA** | `NVDA` | Domina el 80% del mercado de chips para entrenamiento de IA. |
| **TSMC** | `TSM` | El único capaz de fabricar los chips más avanzados de Apple y NVIDIA. |
| **ASML** | `ASML` | Los únicos que fabrican las máquinas (EUV) necesarias para hacer los chips. |
| **ARM** | `ARM` | El diseño de casi todos los procesadores móviles y ahora servidores de IA. |

### 💡 Alternativa Segura: ETFs
Si no quieres elegir una sola empresa, puedes operar el "sector":
- **SMH** (VanEck Semiconductor ETF): Incluye a todas las anteriores.
- **SOXX**: Similar al anterior, muy líquido para trading.

---

## 2. Diferencias Clave con Forex (Nivo FX)
Operar acciones es distinto a operar el EUR/USD. Ten esto en cuenta para tu nuevo bot:

1. **Horarios de Mercado**: A diferencia de las 24/5 de Forex, las acciones se operan principalmente en el horario de Nueva York (**9:30 AM - 4:00 PM EST**). Fuera de eso, la liquidez es baja y peligrosa.
2. **GAPS (Brechas)**: Si una noticia sale en la noche, el precio de la acción puede "saltar" un 5% al abrir. El bot debe saber manejar estos saltos.
3. **Reporte de Ganancias (Earnings)**: Cada 3 meses, la empresa reporta sus números. Aquí es donde ocurren los movimientos masivos (volatilidad extrema). **Regla de Oro:** ¡Cuidado al operar justo antes de un reporte!

---

## 3. Estrategia Sugerida: "Momentum & Pullback"
La misma lógica que acabamos de implementar para el bot de Linux funciona de maravilla en NVDA:

- **La Tendencia es Todo**: En acciones de tecnología, la tendencia suele ser más fuerte y duradera que en Forex.
- **Compra en el Retroceso (Buy the Dip)**: Usar la **EMA 50** y la **EMA 100** como zonas de compra cuando las noticias de IA siguen siendo positivas.

---

## 4. Próximos Pasos Técnicos para el Bot 2.0
Para implementar esto en tu segundo computador portátil, sugiero usar una API distinta a OANDA (ya que OANDA es solo Forex/CFDs):

1. **Alpaca API**: Gratuita para trading algorítmico, fácil de integrar con Python.
2. **Yahoo Finance Engine**: Podemos reutilizar tu motor actual para leer datos técnicos y noticias de Yahoo, pero adaptado a tickets como `NVDA` o `TSM`.

> [!NOTE]
> ¿Te gustaría que empiece a diseñar el prototipo del **AI Stock Watcher** para que lo pruebes en tu otra laptop?
