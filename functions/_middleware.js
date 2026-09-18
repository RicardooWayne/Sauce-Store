/**
 * Modo mantenimiento — apaga el sitio COMPLETO (cualquier ruta) mientras se
 * corrigen los precios. Cloudflare Pages ejecuta este middleware antes que
 * cualquier archivo estatico o funcion, asi que con ACTIVO=true nadie ve el
 * catalogo, solo esta pagina.
 *
 * Para volver a prender el sitio: cambia ACTIVO a false y sube el cambio.
 */
const ACTIVO = false;

const HTML = `<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sauce Store — En mantenimiento</title>
<meta name="robots" content="noindex">
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:#0E0E0E;color:#F4EDDD;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
    Helvetica,Arial,sans-serif;padding:24px;text-align:center}
  .box{max-width:460px}
  .word{font-size:15px;letter-spacing:.22em;text-transform:uppercase;color:#F4EDDD;
    display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:34px;font-weight:700}
  .word i{color:#E8A33D;font-style:normal}
  h1{font-size:clamp(22px,5vw,30px);line-height:1.35;margin:0 0 16px;font-weight:700}
  p{color:#c9c2b4;font-size:15px;line-height:1.6;margin:0 0 30px}
  a.wa{display:inline-flex;align-items:center;gap:10px;background:#E8A33D;color:#0E0E0E;
    text-decoration:none;font-weight:700;padding:14px 22px;border-radius:2px;font-size:15px;
    letter-spacing:.02em}
  a.wa:hover{opacity:.9}
  .tel{display:block;margin-top:16px;color:#F4EDDD;font-size:14px;letter-spacing:.03em}
  .tel b{color:#E8A33D}
</style>
</head>
<body>
  <div class="box">
    <p class="word">SAUCE STORE <i>&#9733;</i></p>
    <h1>Estamos trabajando para mejorar tu experiencia.</h1>
    <p>Volvemos en breve. Si necesitas hacer un pedido urgente, comunicate directo con nosotros.</p>
    <a class="wa" href="https://wa.me/523325883645" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12.04 2c-5.46 0-9.9 4.44-9.9 9.9 0 1.75.46 3.45 1.32 4.95L2 22l5.3-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.9-4.44 9.9-9.9S17.5 2 12.04 2zm5.8 14.01c-.24.68-1.4 1.3-1.94 1.35-.5.05-1.13.24-3.66-.77-3.08-1.22-5.06-4.36-5.22-4.56-.15-.2-1.25-1.66-1.25-3.17 0-1.51.79-2.25 1.07-2.56.28-.31.61-.38.81-.38.2 0 .41 0 .58.01.19.01.44-.07.69.53.24.6.83 2.06.9 2.21.07.15.12.32.02.52-.1.2-.15.32-.3.5-.15.18-.31.4-.44.53-.15.15-.3.31-.13.6.17.29.76 1.25 1.63 2.03 1.12 1 2.06 1.31 2.35 1.46.29.15.46.12.63-.07.17-.2.73-.85.93-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.12.07.7-.17 1.38z"/></svg>
      Escribir por WhatsApp
    </a>
    <span class="tel">O llama/manda mensaje al <b>332 588 3645</b></span>
  </div>
</body>
</html>`;

export async function onRequest(context) {
  if (!ACTIVO) return context.next();
  return new Response(HTML, {
    status: 503,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Retry-After": "7200",
      "Cache-Control": "no-store",
    },
  });
}
