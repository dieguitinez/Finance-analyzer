# Instrucciones para crear un Canal de Solo Lectura para tu Inversor

Para que tu cuñado (u otros inversores) puedan ver las alertas del bot sin poder darle comandos ni ver los payloads de error, debes usar la función de "Canales" de Telegram.

## Pasos en tu celular (Telegram):

1. Abre Telegram y ve a **Chats**.
2. Presiona el botón de crear un nuevo chat (el lápiz) y selecciona **"Nuevo Canal"** (New Channel).
3. Ponle un nombre profesional (ej. **"Nivo FX - Live Trades"**).
4. Dale a siguiente. En la configuración del canal, escoge **"Canal Privado"** (Private Channel).
5. Se te pedirá invitar a personas. **NO invites a nadie todavía**. Continúa y crea el canal vacío.
6. Una vez creado el canal, entra al chat del canal y ve a la configuración (pulsando en el nombre del canal arriba).
7. Ve a la sección de **"Administradores"** (Administrators).
8. Selecciona **"Añadir Administrador"**. Busca el nombre de tu Bot y añádelo. Asígnale permiso únicamente para "Publicar mensajes" (Post messages).

## Cómo configurar el sistema Nivo FX:

Ahora necesitamos decirle al bot que envíe una copia a ese canal.

1. **Obtener el ID del Canal:**
   Ve a Telegram Web o usa un bot como `@RawDataBot` para obtener el ID de tu canal. Si reenvías un mensaje del canal al `@RawDataBot`, te dirá el `id` del forward (suele empezar por `-100`).
   
2. **Actualizar el archivo `.env`:**
   Abre el archivo `.env` de Nivo FX en VS Code y añade esta nueva línea al final:
   
   ```env
   TELEGRAM_BROADCAST_CHAT_ID=-1000000000000
   ```
   *(Reemplaza `-1000000000000` por el ID real de tu canal).*

3. **Invita a tu cuñado:**
   Ve de nuevo a la configuración del canal en Telegram, busca la opción "Enlace de invitación" (Invite Link) y envíaselo a tu cuñado.

¡Listo! A partir del próximo despliegue, cada vez que el bot ejecute un trade o envíe información de mercado, tú lo recibirás en tu chat privado donde puedes usar comandos (`/estado`), y una copia estilizada llegará al canal donde tu cuñado solo podrá leer.
