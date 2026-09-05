#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baja un catalogo del proveedor y lo deja listo para el sitio.

  python tools/importar_proveedor.py --url "<url de la categoria>" \
         --marca "Prada" --modelo "Prada" --tc 2.60

Que hace:
  1. Lee la lista de albumes (cada album = un color).
  2. De cada uno saca el precio en yuanes, el color (en chino) y las tallas EU.
  3. Baja las fotos en alta calidad y las convierte a WebP.
  4. Calcula el precio de venta y traduce el color al espanol.
  5. Escribe todo en productos-extra.json.

IMPORTANTE: nada del proveedor llega al sitio. Ni su nombre, ni el lote, ni
telefonos: solo la foto del par y el precio ya calculado. Hay un filtro que
descarta cualquier producto en cuyo texto se cuele algo de eso.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importar import CARPETAS, EXTRA, procesar_foto, slug, EU_A_MX  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# --- Costos y margen (confirmados con el usuario) --------------------------
ENVIO_YUAN = 270      # se suma al precio del par, en yuanes
COMISION = 1.044      # comision por el pago
MARGEN = 1.40         # 40% de ganancia sobre el costo
REDONDEO = 50         # el precio final se ajusta al multiplo de 50 mas cercano

# --- Palabras del proveedor que NUNCA deben salir en el sitio --------------
CENSURA = re.compile(
    r"rm\s*batch|repsmaster|\brm\b|telegram|whats?app|weidian|@\w+|\+?\d{10,}",
    re.I)

# --- Color en chino -> espanol --------------------------------------------
ACABADOS = {"亮面": "Charol", "磨砂": "Gamuza"}
# El orden importa: los compuestos van antes que los colores sueltos.
COLORES = [
    ("荧光绿", "Verde Neon"),
    ("藏青", "Azul Marino"),
    ("酒红", "Vino"),
    ("浅蓝", "Azul Claro"),
    ("浅绿", "Verde Claro"),
    ("全黑", "Todo Negro"),
    ("黑", "Negro"),
    ("白", "Blanco"),
    ("红", "Rojo"),
    ("灰", "Gris"),
    ("蓝", "Azul"),
    ("绿", "Verde"),
    ("黄", "Amarillo"),
    ("紫", "Morado"),
    ("橙", "Naranja"),
    ("粉", "Rosa"),
    ("棕", "Cafe"),
]


def traducir(txt):
    """'亮面白黑红' -> 'Charol Blanco Negro Rojo'.

    Respeta el orden en que aparecen los colores en el original, no el de la
    tabla: '白黑红' es blanco-negro-rojo, en ese orden.
    """
    acabado = ""
    for zh, es in ACABADOS.items():
        if zh in txt:
            acabado = es
            txt = txt.replace(zh, "")

    # Se marca cada color con su posicion y se tapa para que un color corto
    # no vuelva a coincidir dentro de uno compuesto ya encontrado.
    hallados = []
    resto = txt
    for zh, es in COLORES:
        pos = resto.find(zh)
        while pos != -1:
            hallados.append((pos, es))
            resto = resto[:pos] + ("　" * len(zh)) + resto[pos + len(zh):]
            pos = resto.find(zh)

    colores = [es for _, es in sorted(hallados, key=lambda x: x[0])]
    return " ".join(([acabado] if acabado else []) + colores)


def precio_venta(yuan, tc):
    """Yuanes del proveedor -> (precio de venta, costo), ya redondeado.

    (precio + envio) * comision * tipo_de_cambio = costo
    costo * 1.40 = venta, ajustada al multiplo de 50 mas cercano.
    """
    costo = (yuan + ENVIO_YUAN) * COMISION * tc
    venta = costo * MARGEN
    return int(round(venta / REDONDEO) * REDONDEO), round(costo)


def bajar(url, reintentos=3):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://x.yupoo.com/"})
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if i == reintentos - 1:
                raise
            time.sleep(1.5 * (i + 1))


def leer_albumes(html):
    """Devuelve [(id, titulo)] de la pagina de categoria.

    Se toma la etiqueta <a> completa y de ahi se sacan los atributos, porque
    el orden entre title= y href= no es fijo y hay saltos de linea en medio.
    """
    albums, vistos = [], set()
    for tag in re.findall(r"<a\s[^>]*?/albums/\d+[^>]*?>", html, re.S):
        mh = re.search(r'href="/albums/(\d+)', tag)
        mt = re.search(r'title="([^"]*)"', tag)
        if not mh or mh.group(1) in vistos:
            continue
        vistos.add(mh.group(1))
        albums.append((mh.group(1), mt.group(1) if mt else ""))
    return albums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--marca", required=True, help="categoria en el sitio")
    ap.add_argument("--modelo", default="", help="prefijo del nombre, ej 'Prada'")
    ap.add_argument("--tc", type=float, default=2.60, help="yuan -> peso")
    ap.add_argument("--limite", type=int, default=0, help="solo N (para probar)")
    args = ap.parse_args()

    carpeta_img = CARPETAS.get(args.marca)
    if not carpeta_img:
        print("!! La marca '%s' no esta dada de alta en CARPETAS." % args.marca)
        return

    base = re.match(r"https?://[^/]+", args.url).group(0)
    print("Leyendo el catalogo...")
    albums = leer_albumes(bajar(args.url).decode("utf-8", "replace"))
    if args.limite:
        albums = albums[:args.limite]
    print("  %d colores encontrados\n" % len(albums))

    destino = ROOT / "img" / carpeta_img
    destino.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "_tmp_proveedor"
    tmp.mkdir(exist_ok=True)

    extra = json.loads(EXTRA.read_text(encoding="utf-8")) if EXTRA.exists() else {}
    lista = extra.setdefault(args.marca, [])
    nuevos = actualizados = omitidos = 0

    for i, (aid, titulo) in enumerate(albums, 1):
        try:
            pagina = bajar("%s/albums/%s?uid=1" % (base, aid)).decode("utf-8", "replace")
        except Exception as e:
            print("  !! no se pudo abrir %s: %s" % (aid, e))
            omitidos += 1
            continue

        if not titulo:
            mt = re.search(r"<title>([^<|]*)", pagina)
            titulo = mt.group(1).strip() if mt else ""

        my = re.search(r"(\d+)\s*yuan", titulo, re.I)
        if not my:
            print("  !! sin precio, se omite: %s" % aid)
            omitidos += 1
            continue
        yuan = int(my.group(1))

        # El color queda despues de quitar los corchetes del proveedor
        color_zh = re.sub(r"【[^】]*】", "", titulo).strip()
        color = traducir(color_zh) or "Color"
        nombre = ("%s %s" % (args.modelo, color)).strip()

        ms = re.search(r"Size[:：]\s*([\d\s]+)", pagina)
        tallas = []
        if ms:
            nums = [int(n) for n in ms.group(1).split() if n.isdigit()]
            tallas = ["%s MX (%d EU)" % (EU_A_MX[e], e) for e in nums if e in EU_A_MX]

        cuenta = re.search(r"photo\.yupoo\.com/([a-z0-9_]+)/", pagina)
        hashes = []
        for h in re.findall(r"photo\.yupoo\.com/[a-z0-9_]+/([a-f0-9]{8,})", pagina):
            if h not in hashes:
                hashes.append(h)
        if not hashes or not cuenta:
            print("  !! sin fotos: %s" % nombre)
            omitidos += 1
            continue

        base_slug = slug(nombre)
        galeria = []
        for n, h in enumerate(hashes):
            crudo = tmp / ("%s.jpg" % h)
            try:
                crudo.write_bytes(bajar("https://photo.yupoo.com/%s/%s/large.jpg"
                                        % (cuenta.group(1), h)))
            except Exception:
                continue
            sufijo = "portada" if n == 0 else str(n)
            salida = destino / ("%s-%s.webp" % (base_slug, sufijo))
            procesar_foto(crudo, salida)
            galeria.append("img/%s/%s" % (carpeta_img, salida.name))
            crudo.unlink(missing_ok=True)

        if not galeria:
            print("  !! no se pudo bajar ninguna foto: %s" % nombre)
            omitidos += 1
            continue

        venta, costo = precio_venta(yuan, args.tc)
        registro = {
            "name": nombre, "price": venta, "portada": galeria[0],
            "gallery": galeria, "detail": "p-%s.html" % base_slug,
            "sizes_raw": "", "sizes": tallas,
        }

        # Red de seguridad: si algo del proveedor se colo en el texto, no entra.
        if CENSURA.search(json.dumps(registro, ensure_ascii=False)):
            print("  !! omitido por traer dato del proveedor: %s" % nombre)
            omitidos += 1
            continue

        previo = next((x for x in lista if x["name"] == nombre), None)
        if previo:
            previo.update(registro)
            actualizados += 1
        else:
            lista.append(registro)
            nuevos += 1
        print("  [%2d/%d] %-32s %dY -> costo $%s -> venta $%s  %d fotos  %d tallas"
              % (i, len(albums), nombre, yuan, format(costo, ","),
                 format(venta, ","), len(galeria), len(tallas)))

    EXTRA.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        for f in tmp.iterdir():
            f.unlink(missing_ok=True)
        tmp.rmdir()
    except OSError:
        pass   # OneDrive puede tener la carpeta tomada; no es grave
    print("\nNuevos: %d | Actualizados: %d | Omitidos: %d" % (nuevos, actualizados, omitidos))
    print("Ahora corre:  python tools/build.py")


if __name__ == "__main__":
    main()
