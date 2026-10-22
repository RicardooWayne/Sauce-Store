# -*- coding: utf-8 -*-
"""
Bot de publicaciones de Sauce Store.

Cada corrida: ve que hora es en Mexico, elige el producto que toca, arma la historia
(diseño "foto completa") y la publica:

    12:00 am -> producto del dia (-10%, el mismo que muestra la web)
    10:00 am / 4:00 pm / 8:00 pm -> producto aleatorio

  - Instagram: historia (API oficial de Meta)
  - Facebook: foto en el feed de tu PAGINA, con el link del producto
  - Telegram: te manda la imagen + el texto para compartir a mano en grupos de Facebook
    (publicar en grupos con un bot esta prohibido por Meta y puede costarte la cuenta)

Se configura con variables de entorno (en GitHub: Settings > Secrets). Lo que falte se
omite sin error: sin credenciales el bot solo genera la imagen.

    META_PAGE_TOKEN     token de la pagina (sirve para Facebook e Instagram)
    IG_USER_ID          id de la cuenta de Instagram profesional
    FB_PAGE_ID          id de la pagina de Facebook
    IMGBB_KEY           llave de imgbb.com (Instagram necesita una URL publica de la imagen)
    SOCIAL_TG_TOKEN     token del bot de Telegram (el NUEVO, no el de los pedidos)
    SOCIAL_TG_CHAT_ID   tu chat id de Telegram

Opciones:  --dry-run  genera la imagen y el texto pero NO publica en Instagram ni Facebook
           --slot 0000|1000|1600|2000   fuerza la hora (si no, se detecta sola)
           --date AAAA-MM-DD            fuerza el dia (para pruebas)
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_pick as sp      # noqa: E402
import social_story as ss     # noqa: E402
import social_styles as st    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://" + ss.SITE
GRAPH = "https://graph.facebook.com"
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "").strip()   # vacio = la version mas antigua vigente
OFF = ss.OFF

# hora -> (tipo, posicion en las aleatorias del dia, texto)
SLOTS = {
    "0000": ("dia", None, "12:00 am"),
    "1000": ("rand", 0, "10:00 am"),
    "1600": ("rand", 1, "4:00 pm"),
    "2000": ("rand", 2, "8:00 pm"),
}
MARGEN_MIN = 150   # minutos: si la corrida se atraso mas que esto, no es de ese horario


def env(nombre):
    return (os.environ.get(nombre) or "").strip()


def activo(nombre):
    return env(nombre).lower() not in ("0", "false", "no")


def ahora_mx():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=-6)))     # CDMX no usa horario de verano


def detectar_slot(ahora):
    m = ahora.hour * 60 + ahora.minute
    mejor, dist = None, 10 ** 9
    for clave in SLOTS:
        objetivo = int(clave[:2]) * 60 + int(clave[2:])
        d = min(abs(m - objetivo), 1440 - abs(m - objetivo))
        if d < dist:
            mejor, dist = clave, d
    return mejor if dist <= MARGEN_MIN else None


# --------------------------------------------------------------------------- texto
def money(n):
    return "${:,} MXN".format(int(round(n)))


def armar_texto(prod, url, deal):
    precio = ss.base_price(prod)
    lineas = []
    if deal:
        nuevo = round(precio * (1 - OFF))
        lineas += ["🔥 EL PRODUCTO DEL DÍA · -%d%% SOLO HOY" % int(OFF * 100), "",
                   prod["name"],
                   "Antes %s → AHORA %s" % (money(precio), money(nuevo)),
                   "(el precio cambia a las 12:00 am)"]
    else:
        lineas += [prod["name"], money(precio)]
    tallas = st.tallas_txt(prod.get("sizes"), prefijo="Tallas: ", sep=", ")
    if tallas:
        lineas.append(tallas)
    lineas += ["", "👉 Consíguelo en: " + url,
               "Encarga con el 50% y liquida en la entrega",
               "Instagram: @%s" % st.IG_HANDLE]
    return "\n".join(lineas)


# --------------------------------------------------------------------------- red
class ErrorApi(Exception):
    pass


def _limpiar(txt):
    for k in ("META_PAGE_TOKEN", "IMGBB_KEY", "SOCIAL_TG_TOKEN"):
        v = env(k)
        if v:
            txt = txt.replace(v, "***")
    return txt


def _post(url, datos=None, cabeceras=None, cuerpo=None, timeout=60):
    if cuerpo is None:
        cuerpo = urllib.parse.urlencode(datos or {}).encode()
    req = urllib.request.Request(url, data=cuerpo, headers=cabeceras or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise ErrorApi(_limpiar("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:500])))
    except Exception as e:
        raise ErrorApi(_limpiar(str(e)))


def _get(url, params, timeout=60):
    try:
        with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise ErrorApi(_limpiar("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:500])))
    except Exception as e:
        raise ErrorApi(_limpiar(str(e)))


def graph_url(ruta):
    return "%s/%s%s" % (GRAPH, (GRAPH_VERSION + "/") if GRAPH_VERSION else "", ruta)


def subir_imagen(ruta):
    """Sube la imagen a imgbb (URL publica, se borra sola a los 2 dias)."""
    b64 = base64.b64encode(Path(ruta).read_bytes()).decode()
    r = _post("https://api.imgbb.com/1/upload",
              {"key": env("IMGBB_KEY"), "image": b64, "expiration": 172800})
    url = (r.get("data") or {}).get("url")
    if not url:
        raise ErrorApi("imgbb no devolvio URL: %s" % _limpiar(json.dumps(r)[:300]))
    return url


def publicar_historia_ig(url_img):
    tok, uid = env("META_PAGE_TOKEN"), env("IG_USER_ID")
    c = _post(graph_url("%s/media" % uid),
              {"image_url": url_img, "media_type": "STORIES", "access_token": tok})
    cid = c.get("id")
    if not cid:
        raise ErrorApi("Instagram no creo el contenedor: %s" % json.dumps(c)[:300])
    for _ in range(30):                       # hasta ~90 s
        s = _get(graph_url(cid), {"fields": "status_code", "access_token": tok})
        estado = s.get("status_code")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            raise ErrorApi("Instagram rechazo la imagen (%s)" % estado)
        time.sleep(3)
    p = _post(graph_url("%s/media_publish" % uid), {"creation_id": cid, "access_token": tok})
    return p.get("id")


def publicar_foto_fb(url_img, texto):
    tok, pid = env("META_PAGE_TOKEN"), env("FB_PAGE_ID")
    r = _post(graph_url("%s/photos" % pid), {"url": url_img, "caption": texto, "access_token": tok})
    return r.get("post_id") or r.get("id")


def _multipart(campos, archivos):
    borde = uuid.uuid4().hex
    cuerpo = io.BytesIO()
    for k, v in campos.items():
        cuerpo.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (borde, k, v)).encode())
    for k, (nombre, datos, tipo) in archivos.items():
        cuerpo.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                      "Content-Type: %s\r\n\r\n" % (borde, k, nombre, tipo)).encode())
        cuerpo.write(datos)
        cuerpo.write(b"\r\n")
    cuerpo.write(("--%s--\r\n" % borde).encode())
    return cuerpo.getvalue(), {"Content-Type": "multipart/form-data; boundary=" + borde}


def telegram_foto(ruta, texto):
    tok, chat = env("SOCIAL_TG_TOKEN"), env("SOCIAL_TG_CHAT_ID")
    cuerpo, cab = _multipart({"chat_id": chat, "caption": texto[:1000]},
                             {"photo": ("historia.jpg", Path(ruta).read_bytes(), "image/jpeg")})
    r = _post("https://api.telegram.org/bot%s/sendPhoto" % tok, cuerpo=cuerpo, cabeceras=cab)
    if not r.get("ok"):
        raise ErrorApi("Telegram: %s" % json.dumps(r)[:300])


def telegram_aviso(texto):
    if not (env("SOCIAL_TG_TOKEN") and env("SOCIAL_TG_CHAT_ID")):
        return
    try:
        _post("https://api.telegram.org/bot%s/sendMessage" % env("SOCIAL_TG_TOKEN"),
              {"chat_id": env("SOCIAL_TG_CHAT_ID"), "text": texto[:3500]})
    except ErrorApi:
        pass


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slot", default="auto", help="auto | 0000 | 1000 | 1600 | 2000")
    ap.add_argument("--date", default="", help="AAAA-MM-DD (por defecto, hoy en Mexico)")
    ap.add_argument("--out-dir", default=str(ROOT / "social_out"))
    a = ap.parse_args()
    dry = a.dry_run or env("DRY_RUN").lower() == "true"

    ahora = ahora_mx()
    dia = a.date or ahora.strftime("%Y-%m-%d")
    slot = a.slot if a.slot != "auto" else detectar_slot(ahora)
    if slot not in SLOTS:
        print("Son las %s en Mexico: no es hora de ninguna publicacion (00:00, 10:00, 16:00, 20:00). "
              "Nada que hacer." % ahora.strftime("%H:%M"))
        return 0
    tipo, idx, etiqueta = SLOTS[slot]
    if slot == "0000" and not a.date and ahora.hour >= 12:
        # corrida de medianoche que se adelanto (23:xx): el producto del dia ya es el de manana
        dia = (ahora + timedelta(days=1)).strftime("%Y-%m-%d")

    prods = json.loads((ROOT / "productos.json").read_text(encoding="utf-8"))
    if tipo == "dia":
        pid, deal = sp.deal_of_day(prods, dia), True
    else:
        pid, deal = sp.picks_del_dia(prods, dia)[idx], False

    prod, gal = st.load(pid)
    detalle = (prods[pid].get("url") or "").strip()
    url = "%s/%s" % (SITE_URL, detalle) if detalle else SITE_URL
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = out / ("%s_%s.jpg" % (dia, slot))
    st.st_completa(prod, gal, str(img), deal=deal)
    texto = armar_texto(prod, url, deal)

    print("=== %s · %s · %s ===" % (dia, etiqueta, "PRODUCTO DEL DÍA" if deal else "aleatorio"))
    print("Producto:", prod["name"], "|", prod["cat"], "|", pid)
    print("Imagen:", img)
    print("--- texto ---\n%s\n-------------" % texto)

    quiere_ig = activo("PUBLISH_IG") and env("META_PAGE_TOKEN") and env("IG_USER_ID")
    quiere_fb = activo("PUBLISH_FB") and env("META_PAGE_TOKEN") and env("FB_PAGE_ID")
    quiere_tg = activo("PUBLISH_TG") and env("SOCIAL_TG_TOKEN") and env("SOCIAL_TG_CHAT_ID")
    fallos = []

    # 1) Telegram (a ti): sirve tambien como prueba en modo seco
    if quiere_tg:
        try:
            telegram_foto(img, texto)
            print("Telegram: enviado")
        except ErrorApi as e:
            fallos.append("Telegram: %s" % e)

    # 2) Instagram y Facebook (publico): nunca en modo seco
    if dry:
        print("MODO PRUEBA: no se publica en Instagram ni Facebook.")
        for nombre, ok in (("Instagram", quiere_ig), ("Facebook", quiere_fb)):
            print("  %s: %s" % (nombre, "listo para publicar" if ok else "sin credenciales (se omite)"))
    elif quiere_ig or quiere_fb:
        if not env("IMGBB_KEY"):
            fallos.append("Falta IMGBB_KEY: sin ella no se puede publicar en Instagram/Facebook.")
        else:
            try:
                url_img = subir_imagen(img)
            except ErrorApi as e:
                url_img = None
                fallos.append("Subir imagen: %s" % e)
            if url_img and quiere_ig:
                try:
                    print("Instagram: historia publicada (id %s)" % publicar_historia_ig(url_img))
                except ErrorApi as e:
                    fallos.append("Instagram: %s" % e)
            if url_img and quiere_fb:
                try:
                    print("Facebook: foto publicada (id %s)" % publicar_foto_fb(url_img, texto))
                except ErrorApi as e:
                    fallos.append("Facebook: %s" % e)
    else:
        print("Sin credenciales de Instagram/Facebook: solo se genero la imagen.")

    if fallos:
        msg = "⚠️ Sauce Store bot (%s %s) tuvo problemas:\n- %s" % (dia, etiqueta, "\n- ".join(fallos))
        print(msg)
        telegram_aviso(msg)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
