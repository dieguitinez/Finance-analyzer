# 📊 Análisis de Recursos: Nivo Stock Sentinel (Bot 2.0)

Este análisis detalla lo que tu segunda laptop necesitará para correr el bot de 15 acciones de IA eficientemente.

---

## 1. Perfil de Consumo Estimado
A diferencia de un servidor en la nube, una laptop moderna tiene recursos de sobra para este tipo de tareas.

| Recurso | Consumo (15 Acciones) | Impacto en Laptop |
| :--- | :--- | :--- |
| **RAM** | ~250MB - 400MB | **Mínimo**. Usará menos que una sola pestaña de Google Chrome. |
| **CPU** | 2% - 5% (picos breves) | **Mínimo**. Solo trabaja unos milisegundos cada 60 segundos. |
| **Disco** | ~50MB | **Irrelevante**. Solo para logs y el entorno virtual (`.venv`). |
| **Red** | ~500KB por minuto | **Bajo**. Equivale a enviar un par de fotos por WhatsApp al día. |

---

## 2. Horarios y "Modo Descanso"
Las acciones NO se mueven 24/5 como el Forex. El bot ahorrará recursos automáticamente:

- **Horario Activo**: `9:30 AM - 4:00 PM (EST)`.
- **Pre-Market (Escanéo Silencioso)**: `8:00 AM - 9:30 AM`. Aquí el bot detecta los "Gaps".
- **Modo Sleep**: Fuera de estos horarios, el bot puede entrar en un "Bucle de espera" (Deep Sleep), consumiendo virtualmente **0% de CPU**.

---

## 3. ¿Qué son los "Gaps" (Saltos) y cómo los tratamos?
Los gaps son el mayor riesgo y oportunidad en las acciones. Ocurren porque el mercado cierra, pero el mundo sigue girando.

- **El Reto**: Si NVDA cierra a $120 y en la noche hay una noticia masiva, puede abrir a $125.
- **La Lógica del Bot**: 
    1. A las 9:30 AM, el bot compara el precio de apertura con el cierre de ayer.
    2. Si el "Salto" es muy grande (ej. > 5%), el bot lo marca como **"Anomalía de Apertura"**.
    3. No opera inmediatamente; espera a que el precio se estabilice (usualmente 15-30 min) para ver si es un retroceso (Pullback) o una continuación.

---

## 4. Requisitos de tu Laptop Nueva
Para que este bot corra como un reloj suizo:
- **Procesador**: Cualquier Core i3/Ryzen 3 o superior (mínimo 5 años de antigüedad).
- **RAM**: 8GB es lo ideal para Windows + el Bot.
- **Conexión**: Wi-Fi estable o Cable.
- **S.O.**: Windows 10/11 con permisos de ejecución de scripts activos.

> [!TIP]
> Dado el bajo consumo, incluso podrías tener el **Web Dashboard** abierto en la misma laptop sin que el bot de trading se ralentice.

---

## 5. Análisis de "Co-ubicación" (¿Dos bots en un servidor?)
Considerando que tu hardware real es un **Laptop Físico con Linux, 8GB de RAM y Ryzen 5**:

### Escenario A: Un Solo Hub Institucional (8GB RAM) - RECOMENDADO
- **Carga Total**: Forex (~350MB) + Acciones (~300MB) + Web Dashboard (~250MB) + OS (~500MB) = **~1.4GB**.
- **Margen de Seguridad**: Tienes **~6.6GB de RAM libres**. El procesador Ryzen 5 de 8 núcleos manejará ambos bots con total fluidez.
- **Veredicto**: **Luz Verde Total**. Correr ambos bots en el mismo Linux es la opción más eficiente y centralizada.

### Escenario B: Laptop Secundaria
- **Veredicto**: Solo necesaria si quieres una pantalla física dedicada exclusivamente para ver las gráficas de acciones, pero no es obligatoria por potencia técnica.
