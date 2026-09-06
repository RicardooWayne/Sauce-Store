#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baja catalogos del proveedor (Yupoo) y los deja listos para el sitio.

Modo catalogo (una categoria = varios colores):
  python tools/importar_proveedor.py --url "<url categoria>" \
         --marca "Prada" --modelo "Prada" --tc 2.60

Modo album (un solo album, se eligen fotos por nombre de archivo):
  python tools/importar_proveedor.py --album "<url album>" \
         --marca "Amiri Skeleton" --nombre "Amiri Skeleton Black White" \
         --fotos "a.jpg,b.jpg,c.jpg" --tallas "35 36 37 ... 45" --tc 2.60

Opciones utiles:
  --nombre-fijo "Balenciaga 3XL"   todos los productos llevan ese nombre
                                   (se numera 2,3,4... para que sean distintos)
  --solo-color                     del titulo chino usa SOLO el color, no la
                                   descripcion  (para Uggs)
  --tallas "35 36 ... 46"           tallas EU fijas (no se leen de la pagina)
  --tallas-mx                      tallas MX estandar 25 a 30 (Off White)
  --envio 350                      envio distinto para esta marca (default 270)
  --limite 3                       solo N productos (para probar)

IMPORTANTE: del proveedor NO pasa nada al sitio. Ni su nombre, ni el lote, ni
enlaces, ni telefonos. Hay un filtro (CENSURA) que descarta cualquier producto
en cuyo texto se cuele algo de eso.
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
from importar import CARPETAS, EXTRA, procesar_foto, slug  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# --- Costos y margen (confirmados con el usuario) --------------------------
ENVIO_YUAN = 270      # se suma al precio del par, en yuanes (--envio lo cambia)
COMISION = 1.044      # comision por el pago
MARGEN = 1.40         # 40% de ganancia sobre el costo
REDONDEO = 50         # el precio final se ajusta al multiplo de 50 mas cercano

# --- EU -> MX (tabla Nike Mexico, con medias tallas) ----------------------
EU_A_MX = {
    "35": "22", "35.5": "22.5", "36": "23", "36.5": "23.5", "37": "23.5",
    "37.5": "24", "38": "24", "38.5": "24.5", "39": "24.5", "39.5": "25",
    "40": "25", "40.5": "25.5", "41": "26", "41.5": "26.5", "42": "26.5",
    "42.5": "27", "43": "27.5", "43.5": "28", "44": "28", "44.5": "28.5",
    "45": "29", "45.5": "29.5", "46": "30", "46.5": "30.5", "47": "30.5",
    "47.5": "31", "48": "31",
}


def convertir_tallas(lista_eu):
    """['38','39','40.5'] -> ['24 MX (38 EU)', '24.5 MX (39 EU)', '25.5 MX (40.5 EU)'].

    Guarda la europea junto a la mexicana: asi el pedido que llega por Telegram
    trae el numero con el que hay que pedirle al proveedor.
    """
    out = []
    for eu in lista_eu:
        eu = str(eu).strip().rstrip(".")
        mx = EU_A_MX.get(eu)
        out.append("%s MX (%s EU)" % (mx, eu) if mx else "%s EU" % eu)
    return out


TALLAS_MX = ["25", "25.5", "26", "26.5", "27", "27.5",
             "28", "28.5", "29", "29.5", "30"]

# --- Palabras del proveedor que NUNCA deben salir en el sitio --------------
CENSURA = re.compile(
    r"repsmaster|rmootd|\brm\s*batch\b|telegram|whats?app|weidian|yupoo|"
    r"\byuan\b|@\w+|\+?\d{10,}", re.I)

# --- Traduccion chino -> espanol -----------------------------------------
ACABADOS = {
    "亮面": "Charol", "磨砂": "Gamuza", "反毛皮": "Gamuza", "牛津布": "Oxford",
    "丝绸": "Seda", "牛仔": "Mezclilla", "格子布": "Cuadros",
}
COLORES = [
    ("热带粉", "Rosa Tropical"), ("荧光绿", "Verde Neon"), ("翡翠绿", "Verde Esmeralda"),
    ("藏青", "Azul Marino"), ("酒红", "Vino"), ("香槟", "Champagne"),
    ("胡桃木", "Nogal"), ("栗色", "Castano"), ("沙色", "Arena"), ("米白", "Blanco Hueso"),
    ("米色", "Beige"), ("咖色", "Cafe Claro"), ("褐色", "Marron"), ("深灰", "Gris Oscuro"),
    ("深绿", "Verde Oscuro"), ("浅蓝", "Azul Claro"), ("浅绿", "Verde Claro"),
    ("全黑", "Todo Negro"), ("银粉", "Plata Rosa"), ("白金", "Blanco Dorado"),
    ("彩色", "Multicolor"), ("黑灰", "Negro Gris"), ("灰蓝", "Gris Azul"),
    ("灰绿", "Gris Verde"), ("灰棕", "Gris Marron"), ("灰粉", "Gris Rosa"),
    ("白灰", "Blanco Gris"), ("白红", "Blanco Rojo"), ("白粉", "Blanco Rosa"),
    ("白蓝", "Blanco Azul"), ("白黑", "Blanco Negro"), ("白银", "Blanco Plata"),
    ("黑白", "Negro Blanco"), ("黑银", "Negro Plata"), ("黑棕", "Negro Cafe"),
    ("红灰", "Rojo Gris"), ("黑红", "Negro Rojo"), ("红黑", "Rojo Negro"),
    ("黑", "Negro"), ("白", "Blanco"), ("红", "Rojo"), ("灰", "Gris"),
    ("蓝", "Azul"), ("绿", "Verde"), ("黄", "Amarillo"), ("紫", "Morado"),
    ("橙", "Naranja"), ("粉", "Rosa"), ("棕", "Cafe"), ("银", "Plata"),
    ("金", "Dorado"), ("卡其", "Kaki"),
]
IGNORAR = [
    "民族风", "厚底", "及踝", "低筒", "中筒", "高筒", "高帮", "轮胎", "箭头鞋",
    "绑带", "串珠", "挂饰", "挂链", "满天星", "果冻", "丝绸", "拖鞋", "一脚蹬",
    "毛毛虫", "平底", "拉链", "蝴蝶结", "木扣", "小土豆", "铅笔短靴", "铅笔靴",
    "星拖", "大喜庆", "鱼人坡跟", "坡跟", "短靴", "长靴", "雪地靴", "代", "款",
    "复古", "经典", "新款", "字母",
]


def traducir_color(txt):
    """'亮面白黑红' -> 'Charol Blanco Negro Rojo'. Respeta el orden original."""
    acabado = ""
    for zh, es in ACABADOS.items():
        if zh in txt:
            acabado = es
            txt = txt.replace(zh, "　" * len(zh))
    hallados, resto = [], txt
    for zh, es in COLORES:
        pos = resto.find(zh)
        while pos != -1:
            hallados.append((pos, es))
            resto = resto[:pos] + ("　" * len(zh)) + resto[pos + len(zh):]
            pos = resto.find(zh)
    colores = [es for _, es in sorted(hallados, key=lambda x: x[0])]
    return " ".join(([acabado] if acabado else []) + colores).strip()


CODIGO_RE = re.compile(r"(?!\d{1,3}XL\b)(?=[\w-]*\d)(?=[\w-]*[A-Za-z])[A-Za-z0-9][\w-]{2,}",
                       re.I)


def limpiar_titulo(titulo):
    t = re.sub(r"【[^】]*】", "", titulo)
    t = re.sub(r"\d+\s*(?:yuan|cny|rmb)", "", t, flags=re.I)
    # Separa el chino del texto latino para que un codigo pegado a un caracter
    # chino ("深绿11M91003H") quede como token suelto y se pueda quitar.
    t = re.sub(r"([一-鿿])([A-Za-z0-9])", r"\1 \2", t)
    t = re.sub(r"([A-Za-z0-9])([一-鿿])", r"\1 \2", t)
    # Codigos de estilo del fabricante (DZ7293-800, 1F70191006, 11M91003H,
    # 0ZXSHM191052L...). Es catalogo para clientes: fuera. Se respeta "3XL"/"10XL".
    t = " ".join("" if CODIGO_RE.fullmatch(w) else w for w in t.split())
    # Palabras tecnicas / de lote que a veces se cuelan
    t = re.sub(r"\b(?:batch|item\s*id|id|no|art|sku|code|ref)\b[:：]?\s*\d*",
               " ", t, flags=re.I)
    for w in IGNORAR:
        t = t.replace(w, " ")
    t = re.sub(r"\b1V\b", "LV", t)   # '1V' es censura del proveedor para 'LV'
    return re.sub(r"[\s_/-]+", " ", t).strip(" -_/")


def nombre_producto(modelo, titulo, solo_color):
    limpio = limpiar_titulo(titulo)
    color = traducir_color(limpio)
    if solo_color:
        cuerpo = ("Color " + color) if color else "Color"
    else:
        latin = re.sub(r"[一-鿿]+", "", limpio).strip(" -/")
        cuerpo = " ".join(p for p in [latin, color] if p).strip()
    return re.sub(r"\s+", " ", ("%s %s" % (modelo, cuerpo)).strip())


def leer_precio_yuan(titulo, pagina):
    """Saca el precio en yuanes de '【470yuan】', '【380Y】', '【320】', '¥480', '(480CNY)'.

    Ignora los codigos de estilo (que tambien van entre corchetes y son numeros
    grandes): solo acepta un numero entre 100 y 2000, que es el rango real.
    """
    # 1) numero + unidad de moneda, en cualquier parte
    m = re.search(r"(\d{3,4})\s*(?:yuan|cny|rmb|元|y)\b", titulo + " " + pagina, re.I)
    if m and 100 <= int(m.group(1)) <= 2000:
        return int(m.group(1))
    m = re.search(r"[¥￥$]\s*(\d{3,4})", titulo + " " + pagina)
    if m and 100 <= int(m.group(1)) <= 2000:
        return int(m.group(1))
    # 2) primer corchete del titulo con un numero "de precio"
    for br in re.findall(r"【\s*(\d{3,4})\s*[a-zA-Z]{0,4}\s*】", titulo):
        if 100 <= int(br) <= 2000:
            return int(br)
    return None


def redondear(p):
    """Redondeo del usuario (confirmado 2026-09-05):

        termina en 01-30  -> baja a  ...00
        termina en 31-69  -> queda   ...50
        termina en 70-99  -> sube a  ...00 del siguiente

    Ej: 2018->2000, 2045->2050, 2090->2100.
    """
    p = int(round(p))
    base = p - (p % 100)
    d = p % 100
    if d <= 30:
        return base
    if d <= 69:
        return base + 50
    return base + 100


def precio_venta(yuan, tc, envio):
    costo = (yuan + envio) * COMISION * tc
    return redondear(costo * MARGEN), round(costo)


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
    albums, vistos = [], set()
    for tag in re.findall(r"<a\s[^>]*?/albums/\d+[^>]*?>", html, re.S):
        mh = re.search(r'href="/albums/(\d+)', tag)
        mt = re.search(r'title="([^"]*)"', tag)
        if mh and mh.group(1) not in vistos:
            vistos.add(mh.group(1))
            albums.append((mh.group(1), mt.group(1) if mt else ""))
    return albums


def fotos_del_album(pagina):
    """[(nombre_archivo, hash)] en el orden de la pagina."""
    mc = re.search(r"photo\.yupoo\.com/([a-z0-9_]+)/", pagina)
    if not mc:
        return "", []
    cuenta = mc.group(1)
    out, vistos = [], set()
    for m in re.finditer(
            r'<img[^>]*?alt="([^"]*)"[^>]*?data-(?:origin-)?src="'
            r'https://photo\.yupoo\.com/[a-z0-9_]+/([a-f0-9]{6,})', pagina, re.S):
        nombre, h = m.group(1), m.group(2)
        if h not in vistos:
            vistos.add(h)
            out.append((nombre, h))
    if not out:
        for h in re.findall(r"photo\.yupoo\.com/[a-z0-9_]+/([a-f0-9]{6,})", pagina):
            if h not in vistos:
                vistos.add(h)
                out.append(("", h))
    return cuenta, out


def tallas_de_pagina(pagina):
    """Lee 'Size：38 39 40' o 'SIZE=36 36.5 37.5' -> lista EU."""
    m = re.search(r"size\s*[:：=]\s*([\d.\s]+)", pagina, re.I)
    if not m:
        return []
    return [n for n in m.group(1).split() if re.match(r"^\d+(\.5)?$", n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="url de la categoria")
    ap.add_argument("--album", help="url de un solo album")
    ap.add_argument("--marca", required=True, help="categoria en el sitio")
    ap.add_argument("--modelo", default="", help="prefijo del nombre")
    ap.add_argument("--nombre", default="", help="nombre exacto (modo album)")
    ap.add_argument("--nombre-fijo", dest="nombre_fijo", default="")
    ap.add_argument("--fotos", default="", help="modo album: SOLO estos archivos (coma)")
    ap.add_argument("--omitir", default="", help="modo album: excluir estos archivos (coma)")
    ap.add_argument("--solo-color", dest="solo_color", action="store_true")
    ap.add_argument("--tallas", default="", help="tallas EU fijas, ej '35 36 37 46'")
    ap.add_argument("--tallas-mx", dest="tallas_mx", action="store_true")
    ap.add_argument("--envio", type=int, default=ENVIO_YUAN)
    ap.add_argument("--tc", type=float, default=2.60)
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--solo-precios", dest="solo_precios", action="store_true")
    # --- ropa: precio de venta directo (sin yuanes) + portada por nombre ---
    ap.add_argument("--precio-fijo", dest="precio_fijo", type=int, default=0,
                    help="ropa: precio de venta directo, no lee yuanes")
    ap.add_argument("--portada", default="",
                    help="modo album: nombre de archivo que sera la portada")
    ap.add_argument("--sizes-raw", dest="sizes_raw", default="",
                    help="texto de talla literal, ej 'S a XL' o 'Unitalla'")
    args = ap.parse_args()

    carpeta_img = CARPETAS.get(args.marca)
    if not carpeta_img:
        print("!! La marca '%s' no esta dada de alta en CARPETAS." % args.marca)
        return

    destino = ROOT / "img" / carpeta_img
    destino.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "_tmp_proveedor"
    tmp.mkdir(exist_ok=True)
    extra = json.loads(EXTRA.read_text(encoding="utf-8")) if EXTRA.exists() else {}
    lista = extra.setdefault(args.marca, [])
    # Los costos (yuan/envio) NO van en productos-extra.json porque el repo es
    # publico. Se guardan aparte en tools/_costos.json (gitignored).
    COSTOS = ROOT / "tools" / "_costos.json"
    costos = json.loads(COSTOS.read_text(encoding="utf-8")) if COSTOS.exists() else {}
    costos_marca = costos.setdefault(args.marca, {})

    tallas_fijas = []
    if args.tallas_mx:
        tallas_fijas = TALLAS_MX[:]
    elif args.tallas:
        tallas_fijas = convertir_tallas(re.findall(r"\d+(?:\.5)?", args.tallas))

    base_dom = re.match(r"https?://[^/]+", args.album or args.url).group(0)

    trabajos = []
    if args.album:
        aid = re.search(r"/albums/(\d+)", args.album).group(1)
        filtro = [f.strip() for f in args.fotos.split(",") if f.strip()]
        trabajos.append((aid, args.nombre, filtro))
    else:
        print("Leyendo el catalogo...")
        albums = leer_albumes(bajar(args.url).decode("utf-8", "replace"))
        if args.limite:
            albums = albums[:args.limite]
        print("  %d modelos encontrados\n" % len(albums))
        trabajos = [(aid, t, None) for aid, t in albums]

    seen_base = {}
    nuevos = actualizados = omitidos = 0

    for i, (aid, titulo, filtro) in enumerate(trabajos, 1):
        try:
            pagina = bajar("%s/albums/%s?uid=1" % (base_dom, aid)).decode("utf-8", "replace")
        except Exception as e:
            print("  !! no se pudo abrir %s: %s" % (aid, e)); omitidos += 1; continue

        if not titulo:
            mt = re.search(r"<title>([^<|]*)", pagina)
            titulo = mt.group(1).strip() if mt else ""

        if args.precio_fijo:
            yuan = 0
        else:
            yuan = leer_precio_yuan(titulo, pagina)
            if not yuan:
                print("  !! sin precio, se omite: %s" % (titulo or aid)); omitidos += 1; continue

        if args.nombre:
            base_nombre = args.nombre
        elif args.nombre_fijo:
            base_nombre = args.nombre_fijo
        else:
            base_nombre = nombre_producto(args.modelo, titulo, args.solo_color)
        # Numeracion determinista por orden de album: el 1o queda sin numero,
        # el 2o " 2", etc. Asi el mismo album produce siempre el mismo nombre
        # (importante para --solo-precios, que re-identifica por nombre).
        seen_base[base_nombre] = seen_base.get(base_nombre, 0) + 1
        k = seen_base[base_nombre]
        nombre = base_nombre if k == 1 else "%s %d" % (base_nombre, k)

        if tallas_fijas:
            tallas = tallas_fijas[:]
        else:
            tallas = convertir_tallas(tallas_de_pagina(pagina)) or TALLAS_MX[:]

        if args.solo_precios:
            fotos, cuenta, galeria, base_slug = [], "x", ["_"], "x"
        else:
            cuenta, fotos = fotos_del_album(pagina)
        if filtro and not args.solo_precios:
            pornombre = {nm: h for nm, h in fotos}
            faltan = [f for f in filtro if f not in pornombre]
            if faltan:
                print("  !! fotos no encontradas: %s" % ", ".join(faltan))
            fotos = [(f, pornombre[f]) for f in filtro if f in pornombre]
        # descarta videos/animaciones que el album pueda traer
        fotos = [(nm, h) for nm, h in fotos
                 if not re.search(r"\.(mp4|mov|webm|gif)$", nm, re.I)]
        # --omitir: excluye archivos concretos (match exacto o sin extension)
        if args.omitir and not args.solo_precios:
            om = {o.strip() for o in args.omitir.split(",") if o.strip()}
            om_base = {re.sub(r"\.\w+$", "", o).lower() for o in om}
            fotos = [(nm, h) for nm, h in fotos
                     if nm not in om and re.sub(r"\.\w+$", "", nm).lower() not in om_base]
        # --portada: mueve esa foto al frente (match exacto o sin extension)
        if args.portada and not args.solo_precios:
            pv = args.portada.strip()
            pv_base = re.sub(r"\.\w+$", "", pv).lower()
            idx = next((i for i, (nm, _) in enumerate(fotos)
                        if nm == pv or re.sub(r"\.\w+$", "", nm).lower() == pv_base), None)
            if idx is None:
                print("  !! portada '%s' no esta en el album (%s)" % (pv, nombre))
            else:
                fotos.insert(0, fotos.pop(idx))
        # sin duplicados conservando orden
        _vis, _fu = set(), []
        for nm, h in fotos:
            if h not in _vis:
                _vis.add(h); _fu.append((nm, h))
        fotos = _fu
        if not args.solo_precios and (not fotos or not cuenta):
            print("  !! sin fotos: %s" % nombre); omitidos += 1; continue

        if not args.solo_precios:
            base_slug = slug(nombre) or ("prod-%s" % aid)
            galeria = []
        for k, (nm, h) in enumerate(fotos):
            crudo = tmp / ("%s.jpg" % h)
            try:
                crudo.write_bytes(bajar("https://photo.yupoo.com/%s/%s/large.jpg" % (cuenta, h)))
            except Exception:
                continue
            sufijo = "portada" if k == 0 else str(k)
            salida = destino / ("%s-%s.webp" % (base_slug, sufijo))
            procesar_foto(crudo, salida)
            galeria.append("img/%s/%s" % (carpeta_img, salida.name))
            crudo.unlink(missing_ok=True)
        if not args.solo_precios and not galeria:
            print("  !! no se pudo bajar ninguna foto: %s" % nombre); omitidos += 1; continue

        if args.precio_fijo:
            venta, costo = args.precio_fijo, 0
        else:
            venta, costo = precio_venta(yuan, args.tc, args.envio)

        # --solo-precios: no baja fotos, solo actualiza el precio del producto
        # que ya existe (para recalcular con otra formula/redondeo).
        if args.solo_precios:
            previo = next((x for x in lista if x["name"] == nombre), None)
            if previo:
                antes = previo.get("price")
                previo["price"] = venta
                costos_marca[nombre] = {"yuan": yuan, "envio": args.envio}
                actualizados += 1
                if antes != venta:
                    print("  %-42s $%s -> $%s  (%dY)" % (nombre[:42], antes, venta, yuan))
            else:
                print("  ?? no existe (nombre no coincide): %s" % nombre)
            continue

        registro = {
            "name": nombre, "price": venta,
            "portada": galeria[0], "gallery": galeria,
            "detail": "p-%s.html" % base_slug,
            "sizes_raw": args.sizes_raw, "sizes": [] if args.sizes_raw else tallas,
        }
        if not args.precio_fijo:
            costos_marca[nombre] = {"yuan": yuan, "envio": args.envio}
        if CENSURA.search(json.dumps(registro, ensure_ascii=False)):
            print("  !! omitido por dato del proveedor: %s" % nombre); omitidos += 1; continue

        previo = next((x for x in lista if x["name"] == nombre), None)
        if previo:
            previo.update(registro); actualizados += 1
        else:
            lista.append(registro); nuevos += 1
        print("  [%3d/%d] %-42s %dY -> $%s  %d fotos  %d tallas"
              % (i, len(trabajos), nombre[:42], yuan, format(venta, ","),
                 len(galeria), len(tallas)))

    EXTRA.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
    COSTOS.write_text(json.dumps(costos, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        for f in tmp.iterdir():
            f.unlink(missing_ok=True)
        tmp.rmdir()
    except OSError:
        pass
    print("\nNuevos: %d | Actualizados: %d | Omitidos: %d" % (nuevos, actualizados, omitidos))
    print("Ahora corre:  python tools/build.py")


if __name__ == "__main__":
    main()
