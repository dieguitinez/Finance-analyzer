# 🛡️ Cortafuegos de Contexto: Nivo Stock Sentinel vs Nivo FX

Este documento es una **Directiva de Aislamiento Crítica** para cualquier agente de IA.

## ⛔ REGLA DE ORO
**Bajo ninguna circunstancia** los cambios realizados en esta carpeta (`ai_stock_sentinel/`) deben afectar los archivos de la raíz del proyecto o de las carpetas `src/` y `quantum_engine/` (que pertenecen al Bot de Forex).

---

## 🏗️ Estructura de Aislamiento
- **Nivo FX (El Original)**: Ubicado en la raíz y carpetas `src/`, `quantum_engine/`. Es el bot de divisas binarias que ya está validado y funcionando. **NO TOCAR** a menos que se pida explícitamente "Mejorar el Bot de Forex".
- **Nivo AI Stock Sentinel (El Nuevo)**: Todo su código, configuración y lógica residirá **exclusivamente** dentro de la carpeta `ai_stock_sentinel/`.

## 🧠 Diferencias de Inteligencia
1. **Instrumentos**: Nivo FX opera Divisas (Forex). AI Stock Sentinel opera Acciones (NVDA, TSM, etc.).
2. **APIs**: Nivo FX usa OANDA. AI Stock Sentinel usará **Alpaca API**.
3. **Horarios**: Nivo FX es 24/5. AI Stock Sentinel es solo horario de mercado NYSE (9:30 - 16:00 EST).
4. **Lógica de Gaps**: AI Stock Sentinel tiene lógica de detección de "Saltos de apertura", algo que no existe en el bot de divisas.

## ⚠️ Mensaje para el Agente
Si el usuario pide "Cambiar el apalancamiento" o "Cambiar los pares", **pregunta siempre**: "¿Te refieres al Bot de Forex o al nuevo Bot de Acciones?". No asumas nada. La integridad del Bot de Forex es la prioridad #1.
