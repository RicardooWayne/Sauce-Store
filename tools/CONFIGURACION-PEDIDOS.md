# Configuración del sistema de pedidos

Son 3 pasos. Hazlos una sola vez y ya queda para siempre.

Mientras no los hagas, la página **sí funciona**: genera el ticket normal, nada más
que a ti no te llega el aviso. Nadie pierde su pedido, simplemente no te enteras.

---

## 1. Bot de Telegram (para que te lleguen los pedidos)

**a) Crear el bot**
1. Abre Telegram y busca **@BotFather**.
2. Mándale `/newbot`.
3. Te pide un nombre: pon `Sauce Store Pedidos`.
4. Te pide un usuario: tiene que terminar en `bot`, por ejemplo `saucestore_pedidos_bot`.
5. Te responde con un **token**, algo así:
   `8123456789:AAF-abc123DEF456ghi789JKL`
   👉 **Ese es tu `TELEGRAM_BOT_TOKEN`.** No se lo pases a nadie.

**b) Sacar tu chat id**
1. Búscate a tu propio bot en Telegram (el usuario que elegiste) y dale **Iniciar**.
2. Mándale cualquier mensaje, por ejemplo `hola`.
3. Abre esta dirección en el navegador, cambiando `TU_TOKEN` por el token de arriba:
   ```
   https://api.telegram.org/botTU_TOKEN/getUpdates
   ```
   > Es normal que el token vaya en la URL, es la única forma con este método.
   > Solo no tomes captura de esta pantalla ni la compartas: ahí se ve completo.
   > Si ya lo hiciste, no pasa nada — al terminar haz `/revoke` en BotFather y
   > te da uno nuevo.

4. Busca en el texto algo como `"chat":{"id":123456789,`
   👉 **Ese número es tu `TELEGRAM_CHAT_ID`.**

   ¿Te sale `{"ok":true,"result":[]}` (vacío)? Es porque el bot todavía no
   recibe mensajes. Vuelve al paso 2: búscalo en Telegram, dale **Iniciar** y
   mándale un `hola`. Luego recarga esta página.

> ¿Quieres que los pedidos lleguen a un grupo con tu equipo? Crea el grupo, mete al
> bot, manda un mensaje en el grupo y repite el paso 3. El id del grupo es negativo
> (empieza con `-100...`). Funciona igual.

---

## 2. Hoja de Excel (Google Sheets)

1. Entra a **https://sheets.new** y ponle de nombre `Pedidos Sauce Store`.
2. Menú **Extensiones → Apps Script**.
3. Borra todo lo que salga y pega el contenido completo de
   [`tools/sheets-webhook.gs`](sheets-webhook.gs).
4. En la línea `const SECRETO = "cambia-esta-palabra";` pon una palabra tuya.
   👉 Esa palabra es tu `SHEETS_SECRET`. Anótala.
5. Botón **Implementar → Nueva implementación**:
   - Tipo: **Aplicación web**
   - Ejecutar como: **Yo**
   - Quién tiene acceso: **Cualquier persona**
6. Te da una URL que termina en `/exec`.
   👉 **Esa es tu `SHEETS_WEBHOOK_URL`.**

**Para bajarla como Excel:** en la hoja, `Archivo → Descargar → Microsoft Excel (.xlsx)`.

---

## 3. Cargar los datos en Cloudflare

1. Entra a **https://dash.cloudflare.com** → **Workers & Pages** → tu proyecto `sauce-store`.
2. **Settings → Environment variables → Production → Add variable.**
3. Agrega estas 4, una por una (marca **Encrypt** en todas):

| Nombre | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | el token del paso 1a |
| `TELEGRAM_CHAT_ID` | el número del paso 1b |
| `SHEETS_WEBHOOK_URL` | la URL `/exec` del paso 2 |
| `SHEETS_SECRET` | la palabra secreta del paso 2 |

4. **Save** y vuelve a desplegar (Deployments → Retry deployment), para que tome
   las variables nuevas.

⚠️ **Importante:** estas 4 cosas NUNCA van en el código ni en GitHub. Van solo aquí.
Si alguna se te llega a filtrar, se cambia y listo (en BotFather con `/revoke`).

---

## Probar que quedó

1. Entra a tu sitio, agrega algo al carrito y genera un ticket de prueba.
2. Debe pasar todo esto:
   - Te sale el ticket con folio en pantalla
   - Te llega el mensaje a Telegram con los datos
   - Aparece una fila nueva en la hoja de Google

Si el ticket sale pero no llega a Telegram: revisa que el token y el chat id estén
bien escritos y que hayas vuelto a desplegar.

---

## Notas

- **No hay cobro en línea.** El método de pago es solo para que tú sepas cómo te van
  a pagar. Tú cobras aparte, como siempre.
- Los precios se calculan **en el servidor** contra el catálogo. Aunque alguien
  edite el carrito desde su navegador, no puede cambiar un precio.
- La dirección solo se pide cuando el pedido es con envío.
- Los datos del cliente viajan cifrados (HTTPS) y solo llegan a tu Telegram y a tu hoja.
