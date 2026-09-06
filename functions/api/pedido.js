/**
 * POST /api/pedido — recibe un pedido, lo valida, arma el ticket y avisa.
 *
 * Cloudflare Pages ejecuta este archivo automaticamente (carpeta /functions).
 *
 * REGLA DE ORO: nada de lo que manda el navegador se cree sin verificar.
 * Los precios NO viajan en la peticion: el navegador solo manda {id, size, qty}
 * y aqui se resuelven contra productos.json. Asi, aunque alguien edite el
 * carrito o el JavaScript en su navegador, no puede cambiar un precio.
 *
 * Variables de entorno (Cloudflare Pages > Settings > Environment variables):
 *   TELEGRAM_BOT_TOKEN   token del bot de @BotFather
 *   TELEGRAM_CHAT_ID     id del chat donde caen los pedidos
 *   SHEETS_WEBHOOK_URL   URL del Apps Script de la hoja de calculo
 *   SHEETS_SECRET        palabra secreta compartida con ese script
 * Si faltan, el pedido igual genera ticket (modo prueba) y se avisa en el log.
 */

const REENVIO_APARTADO = 200;
const COMISION_TARJETA = 0.05;
const MAX_ITEMS = 30;
const MAX_QTY = 10;
const MIN_MS = 3000; // llenar el formulario en menos de 3s = bot
const MAX_PEDIDOS_VENTANA = 8;  // pedidos permitidos por IP...
const VENTANA_SEG = 600;        // ...cada 10 minutos

const MODOS = ["apartado", "liquidar"];
const ENTREGAS = ["gdl", "envio"];
const PAGOS = ["transferencia", "oxxo", "tarjeta"];
const DIR_REQ = ["estado", "ciudad", "calle", "colonia", "numero", "entrecalles"];
const DIR_OPC = ["cp", "referencias"];

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });

const bad = (msg) => json({ error: msg }, 400);

/** Recorta, normaliza espacios y quita caracteres de control. */
function clean(v, max) {
  return String(v == null ? "" : v)
    .replace(/[\u0000-\u001F\u007F]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max);
}

/** Escapa para el HTML de Telegram (evita que un nombre rompa el mensaje). */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const money = (n) => "$" + Math.round(n).toLocaleString("es-MX") + " MXN";

function folio() {
  const d = new Date();
  const ymd =
    String(d.getUTCFullYear()).slice(2) +
    String(d.getUTCMonth() + 1).padStart(2, "0") +
    String(d.getUTCDate()).padStart(2, "0");
  const rnd = Array.from(crypto.getRandomValues(new Uint8Array(2)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
  return `SS-${ymd}-${rnd}`;
}

/* Este endpoint solo recibe pedidos (POST). Abrirlo en el navegador no muestra nada. */
export function onRequestGet() {
  return json({ error: "Metodo no permitido." }, 405);
}

export async function onRequestPost(context) {
  const { request, env } = context;

  let body;
  try {
    body = await request.json();
  } catch {
    return bad("Peticion invalida.");
  }

  /* ---------- anti-spam ---------- */
  if (clean(body.hp, 50)) return json({ ok: true, ticket: null }); // honeypot
  if (typeof body.ms === "number" && body.ms < MIN_MS)
    return bad("Formulario enviado demasiado rapido.");

  // Freno por IP: evita que alguien inunde el Telegram con pedidos falsos.
  // Usa el cache de Cloudflare como contador (no necesita base de datos).
  const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";
  if (!(await underLimit(ip))) {
    return json({ error: "Demasiados pedidos seguidos. Espera unos minutos." }, 429);
  }

  /* ---------- campos de seleccion ---------- */
  const modo = MODOS.includes(body.modo) ? body.modo : null;
  const entrega = ENTREGAS.includes(body.entrega) ? body.entrega : null;
  const pago = PAGOS.includes(body.pago) ? body.pago : null;
  if (!modo || !entrega || !pago) return bad("Opciones de pedido invalidas.");

  /* ---------- datos del cliente ---------- */
  const nombre = clean(body.nombre, 80);
  if (nombre.length < 2) return bad("El nombre no es valido.");

  const whatsapp = String(body.whatsapp || "").replace(/\D/g, "");
  if (whatsapp.length !== 10) return bad("El WhatsApp debe tener 10 digitos.");

  let direccion = null;
  if (entrega === "envio") {
    direccion = {};
    for (const k of DIR_REQ) {
      const v = clean(body.direccion?.[k], 120);
      if (v.length < 2) return bad(`Falta un dato de la direccion: ${k}.`);
      direccion[k] = v;
    }
    for (const k of DIR_OPC) direccion[k] = clean(body.direccion?.[k], 120);
  }

  /* ---------- productos: se resuelven contra el catalogo ---------- */
  if (!Array.isArray(body.items) || !body.items.length)
    return bad("El carrito esta vacio.");
  if (body.items.length > MAX_ITEMS) return bad("Demasiados productos.");

  const origin = new URL(request.url).origin;
  let catalogo;
  try {
    catalogo = await (await fetch(`${origin}/productos.json`)).json();
  } catch {
    return json({ error: "No se pudo leer el catalogo." }, 500);
  }

  const items = [];
  for (const raw of body.items) {
    const p = catalogo[clean(raw.id, 120)];
    if (!p) return bad("Uno de los productos ya no esta disponible.");

    const qty = Math.min(Math.max(parseInt(raw.qty, 10) || 1, 1), MAX_QTY);
    const size = clean(raw.size, 40);
    if (!size) return bad(`Falta la talla de ${p.name}.`);
    // Si el producto tiene lista cerrada de tallas, la talla debe estar en ella
    if (Array.isArray(p.sizes) && p.sizes.length && !p.sizes.includes(size))
      return bad(`Talla no valida para ${p.name}.`);

    // Opcion dentro del producto (color, o "solo hoodie / solo pants").
    // Si el producto tiene opciones, hay que elegir una; el precio sale de ahi.
    let price = p.price;
    let opt = "";
    if (p.options && Array.isArray(p.options.choices) && p.options.choices.length) {
      opt = clean(raw.opt, 60);
      const ch = p.options.choices.find((c) => c.name === opt);
      if (!ch) return bad(`Falta elegir una opcion de ${p.name}.`);
      if (typeof ch.price === "number") price = ch.price;
    }

    items.push({
      name: p.name,
      cat: p.cat,
      size,
      opt,
      qty,
      price,              // <- precio del catalogo, no el del navegador
      line: price * qty,
    });
  }

  /* ---------- totales (se calculan aqui, siempre) ---------- */
  const subtotal = items.reduce((s, i) => s + i.line, 0);
  const reenvio = modo === "apartado" && entrega === "envio" ? REENVIO_APARTADO : 0;
  const base = subtotal + reenvio;
  const comision = pago === "tarjeta" ? Math.round(base * COMISION_TARJETA) : 0;
  const total = base + comision;
  const ahora =
    modo === "apartado" ? Math.round(subtotal / 2) + reenvio + comision : total;
  const totales = {
    subtotal,
    reenvio,
    comision,
    total,
    ahora,
    resta: modo === "apartado" ? total - ahora : 0,
  };

  const ticket = {
    folio: folio(),
    fecha: new Date().toISOString(),
    nombre,
    whatsapp,
    modo,
    entrega,
    pago,
    direccion,
    items,
    totales,
  };

  /* ---------- avisos (no deben tumbar el pedido si fallan) ---------- */
  await Promise.allSettled([notifyTelegram(env, ticket), saveToSheet(env, ticket)]);

  return json({ ok: true, ticket });
}

/**
 * Limite por IP usando el cache de Cloudflare como contador.
 * Guarda cuantos pedidos lleva esa IP en la ventana actual; si se pasa,
 * rechaza. No necesita base de datos ni configuracion extra.
 */
async function underLimit(ip, max = MAX_PEDIDOS_VENTANA, ventanaSeg = VENTANA_SEG) {
  try {
    const cache = caches.default;
    const key = new Request(`https://ratelimit.local/pedido/${encodeURIComponent(ip)}`);
    const hit = await cache.match(key);
    const n = hit ? parseInt(await hit.text(), 10) || 0 : 0;
    if (n >= max) return false;
    await cache.put(
      key,
      new Response(String(n + 1), {
        headers: { "Cache-Control": `max-age=${ventanaSeg}` },
      })
    );
    return true;
  } catch {
    return true; // si el cache falla, no bloqueamos pedidos legitimos
  }
}

async function notifyTelegram(env, t) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;

  const lineas = t.items
    .map((i) => `• ${i.qty}× ${esc(i.name)}${i.opt ? ` <i>(${esc(i.opt)})</i>` : ""} — <b>talla ${esc(i.size)}</b> — ${money(i.line)}`)
    .join("\n");

  const dir = t.direccion
    ? `\n\n<b>Direccion</b>\n${esc(
        [t.direccion.calle, t.direccion.numero, t.direccion.colonia,
         t.direccion.ciudad, t.direccion.estado, t.direccion.cp]
          .filter(Boolean).join(", ")
      )}\nEntre calles: ${esc(t.direccion.entrecalles)}` +
      (t.direccion.referencias ? `\nRef: ${esc(t.direccion.referencias)}` : "")
    : "";

  const pagos = { transferencia: "Transferencia", oxxo: "Deposito OXXO", tarjeta: "Tarjeta (+5%)" };
  const extras =
    (t.totales.reenvio ? `\nReenvio: ${money(t.totales.reenvio)}` : "") +
    (t.totales.comision ? `\nComision tarjeta: ${money(t.totales.comision)}` : "");

  const msg =
    `🧾 <b>NUEVO PEDIDO</b>  <code>${t.folio}</code>\n\n` +
    `<b>${esc(t.nombre)}</b>\n` +
    `📱 <a href="https://wa.me/52${t.whatsapp}">${t.whatsapp}</a>\n\n` +
    `${lineas}\n` +
    `\nSubtotal: ${money(t.totales.subtotal)}${extras}` +
    `\n<b>Total: ${money(t.totales.total)}</b>` +
    `\n💰 Cobrar ahora: <b>${money(t.totales.ahora)}</b>` +
    (t.totales.resta ? `\nResta al recibir: ${money(t.totales.resta)}` : "") +
    `\n\nModalidad: ${t.modo === "apartado" ? "Apartado 50%" : "Liquidado"}` +
    `\nEntrega: ${t.entrega === "envio" ? "Envio a domicilio" : "Guadalajara"}` +
    `\nPago: ${pagos[t.pago]}` +
    dir;

  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text: msg,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
}

async function saveToSheet(env, t) {
  if (!env.SHEETS_WEBHOOK_URL) return;
  const d = t.direccion || {};
  await fetch(env.SHEETS_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      secret: env.SHEETS_SECRET || "",
      fecha: t.fecha,
      folio: t.folio,
      nombre: t.nombre,
      whatsapp: t.whatsapp,
      modalidad: t.modo === "apartado" ? "Apartado 50%" : "Liquidado",
      entrega: t.entrega === "envio" ? "Envio" : "Guadalajara",
      pago: t.pago,
      productos: t.items
        .map((i) => `${i.qty}x ${i.name}${i.opt ? ` [${i.opt}]` : ""} (talla ${i.size})`)
        .join(" | "),
      subtotal: t.totales.subtotal,
      reenvio: t.totales.reenvio,
      comision: t.totales.comision,
      total: t.totales.total,
      cobrar_ahora: t.totales.ahora,
      resta: t.totales.resta,
      estado: d.estado || "",
      ciudad: d.ciudad || "",
      calle: d.calle || "",
      colonia: d.colonia || "",
      numero: d.numero || "",
      entrecalles: d.entrecalles || "",
      cp: d.cp || "",
      referencias: d.referencias || "",
    }),
  });
}
