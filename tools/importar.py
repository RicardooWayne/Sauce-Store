#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importa productos nuevos desde capturas, sin tocar codigo.

COMO USARLO
-----------
1. Crea la carpeta NUEVOS/ en el proyecto (si no existe).
2. Adentro, una carpeta por marca, y dentro una carpeta por modelo con el
   formato  "Nombre del modelo - PRECIO":

       NUEVOS/
       |- Jordan 4/
       |  |- Black Cat - 2900/
       |  |     lo-que-sea-1.jpg   <- primera foto = portada
       |  |     lo-que-sea-2.jpg
       |  |- Military Blue - 2850/
       |        foto.png
       |- Bape/
          |- Shark Full Zip Verde - 1450/
                a.jpg  b.jpg

   Si quieres elegir la portada a mano, nombra esa foto empezando con
   "portada" (portada.jpg, portada-1.png, etc).

   Las tallas son opcionales. Si no pones nada, se usan las de la marca
   (los tenis toman 25 a 30 MX). Para forzarlas, agregalas al final:

       "Shark Full Zip Verde - 1450 - S a XL"
       "Pantalon Cargo - 1250 - 30-32-34-36"

3. Corre:   python tools/importar.py
4. Luego:   python tools/build.py

Las capturas originales se quedan en NUEVOS/ (no se suben a la web).
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
NUEVOS = ROOT / "NUEVOS"
EXTRA = ROOT / "productos-extra.json"
MAX_LADO = 1400
CALIDAD = 82
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# Marca -> carpeta de imagenes. Las que ya existen en el sitio.
CARPETAS = {
    "Jordan 1": "Jordan-1", "Jordan 3": "Jordan-3", "Jordan 4": "Jordan-4",
    "Jordan 5": "Jordan-5", "Jordan 6": "Jordan-6", "Jordan 10": "Jordan-10",
    "Jordan 11": "Jordan-11", "Rick Owens": "Rick-Owens",
    "Louis Vuitton": "Louis-Vuitton", "Maison Margiela": "Maison-Margiela",
    "Golden Goose": "Golden-Goose", "Prada": "Prada",
    "Balenciaga Defender": "Balenciaga-Defender",
    "Balenciaga 3XL": "Balenciaga-3XL",
    "Balenciaga 6XL": "Balenciaga-6XL",
    "Balenciaga 10XL": "Balenciaga-10XL",
    "Balenciaga Basketball": "Balenciaga-Basketball",
    "Balenciaga Runner": "Balenciaga-Runner",
    "Nocta": "Nocta",
    "Uggs": "Uggs",
    "Nike Dunk": "Nike-Dunk",
    "Bapesta": "Bapesta",
    "Timberland": "Timberland",
    "Off White": "Off-White",
    "Amiri": "Amiri-Tenis", "Dior": "Dior",
    "Alexander McQueen": "Alexander-McQueen", "Balenciaga": "Balenciaga",
    "Bape": "Bape", "Burberry": "Burberry", "Supreme": "Supreme", "Nike": "Nike-Ropa",
    "Chrome Hearts": "Chrome-Hearts-Ropa",
    "Chrome Hearts Cadenas": "Chrome-Hearts-Cadenas",
    "Stock": "Stock",
}


def slug(s):
    s = re.sub(r"[^\w\s-]", "", s, flags=re.U).strip().lower()
    return re.sub(r"[\s_]+", "-", s)


def recortar_bordes(im, tolerancia=12):
    """Quita el borde liso de una captura (barras blancas/grises de los lados).

    Solo recorta si el borde es claramente de un color parejo; si la foto ya
    viene ajustada, la deja igual.
    """
    rgb = im.convert("RGB")
    fondo = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    dif = ImageChops.difference(rgb, fondo).convert("L").point(
        lambda p: 255 if p > tolerancia else 0)
    caja = dif.getbbox()
    if not caja:
        return im
    an, al = caja[2] - caja[0], caja[3] - caja[1]
    # Si el recorte se comeria mas de la mitad, algo salio mal: no tocar.
    if an < im.width * 0.5 or al < im.height * 0.5:
        return im
    return im.crop(caja)


def procesar_foto(origen, destino):
    im = Image.open(origen)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if im.mode == "P" else "RGB")
    im = recortar_bordes(im)
    im.thumbnail((MAX_LADO, MAX_LADO), Image.LANCZOS)
    im.save(destino, "WEBP", quality=CALIDAD, method=5)


def leer_carpeta_producto(carpeta):
    """Lee el nombre de la carpeta.

        'Black Cat - 2900'              -> ('Black Cat', 2900, '')
        'Shark Zip - 1450 - S a XL'     -> ('Shark Zip', 1450, 'S a XL')

    Las tallas son opcionales: si no las pones, se usan las de la marca.
    """
    txt = carpeta.name.strip()
    m = re.match(r"^(.*?)\s*[-–]\s*\$?\s*([\d,]+)\s*(?:[-–]\s*(.+))?$", txt)
    if not m:
        return None, None, None
    nombre = re.sub(r"\s+", " ", m.group(1)).strip()
    precio = int(m.group(2).replace(",", ""))
    tallas = (m.group(3) or "").strip()
    return (nombre, precio, tallas) if nombre else (None, None, None)



# ---------------------------------------------------------------------------
# Modo "archivos sueltos": una carpeta con las fotos nombradas
#     NOMBRE DEL MODELO<numero>-$PRECIO.png
# ejemplo:  RICK OWENS GEOBASKET1-$3600.png
# El numero indica el orden de la galeria; el 1 es la portada.
# ---------------------------------------------------------------------------
# Equivalencia EU -> MX (tabla Nike Mexico, la estandar para tenis en el pais).
# Confirmada con el usuario el 2026-09-05.
EU_A_MX = {
    35: "22", 36: "23", 37: "23.5", 38: "24", 39: "24.5", 40: "25", 41: "26",
    42: "26.5", 43: "27.5", 44: "28", 45: "29", 46: "30", 47: "30.5",
}

# Siglas que se quedan en mayusculas
SIGLAS = {"LJR", "OG", "QC", "SB", "GG", "NY", "LA", "XL", "TS", "OVO", "AJ", "LV"}
# Palabras de union que van en minuscula (salvo al inicio)
MENORES = {"con", "de", "del", "y", "la", "el", "en", "para", "sin", "a"}

# Nombre + numero de foto + precio, tolerante a como se separen:
#   "LV Buttersoft Blancos1-$3100 TALLAS 40-45 EU"
#   "Maison Margiela Replica Cafe1 $2300 40 a 47 EU"
#   "Golden Goose Super Star Blancos1-$2300- TALLAS EU 35-45"
RE_PRECIO = re.compile(r"\$\s*([\d,]+)")
RE_NUM_FINAL = re.compile(r"^(.+?)(\d+)$")
RE_RANGO_EU = re.compile(r"(\d{2})\s*(?:-|a|hasta|to)\s*(\d{2})", re.I)


def bonito(nombre):
    """'LV SKATE AZUL' -> 'LV Skate Azul'; respeta siglas y palabras de union."""
    out = []
    for i, w in enumerate(nombre.split()):
        if w.upper() in SIGLAS:
            out.append(w.upper())
        elif i > 0 and w.lower() in MENORES:
            out.append(w.lower())
        elif w.isupper():
            out.append(w.capitalize())      # "AZUL" -> "Azul"
        else:
            out.append(w[0].upper() + w[1:])  # respeta como ya venia escrito
    return " ".join(out)


def tallas_desde_rango(desde, hasta):
    """EU 40-45 -> ['25 MX (40 EU)', '26 MX (41 EU)', ...].

    Se guarda la talla europea junto a la mexicana para que, al llegar el
    pedido, se pueda pedir al proveedor con el numero exacto sin convertir
    de cabeza.
    """
    salida = []
    for eu in range(int(desde), int(hasta) + 1):
        mx = EU_A_MX.get(eu)
        salida.append(f"{mx} MX ({eu} EU)" if mx else f"{eu} EU")
    return salida


def leer_nombre_plano(archivo):
    """Saca (nombre, orden de foto, precio, tallas) del nombre del archivo."""
    stem = archivo.stem.strip()
    mp = RE_PRECIO.search(stem)
    if not mp:
        return None, None, None, None
    precio = int(mp.group(1).replace(",", ""))

    antes = stem[:mp.start()].strip(" -")
    mn = RE_NUM_FINAL.match(antes)
    if not mn:
        return None, None, None, None
    nombre = re.sub(r"\s+", " ", mn.group(1)).strip(" -")
    orden = int(mn.group(2))

    mr = RE_RANGO_EU.search(stem[mp.end():])
    tallas = tallas_desde_rango(mr.group(1), mr.group(2)) if mr else []
    return nombre, orden, precio, tallas



def orden_natural(nombre):
    """Ordena 'foto2' antes que 'foto10' (el orden que espera una persona)."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", nombre)]


def tallas_desde_texto(txt):
    """'EU 40-45' -> lista MX(EU).  'S a XL' -> se deja tal cual para build.py."""
    if not txt:
        return None
    m = RE_RANGO_EU.search(txt)
    if m and re.search(r"eu", txt, re.I):
        return tallas_desde_rango(m.group(1), m.group(2))
    return None


def importar_carpetas(raiz, marca, extra, precio_def=None, tallas_def=None):
    """Una subcarpeta = un modelo. Las fotos de adentro van en orden natural.

    El nombre de la carpeta puede ser solo el modelo ('Super Star Gold') si se
    pasan --precio y --tallas, o traer los datos ('Super Star Gold - 2300 - EU 35-45').
    """
    carpeta_img = CARPETAS.get(marca)
    if not carpeta_img:
        print(f"  !! marca desconocida: '{marca}'")
        return 0, 0

    destino_dir = ROOT / "img" / carpeta_img
    destino_dir.mkdir(parents=True, exist_ok=True)
    nuevos = actualizados = 0

    for sub in sorted([d for d in raiz.iterdir() if d.is_dir()],
                      key=lambda d: orden_natural(d.name)):
        nombre, precio, tallas_txt = leer_carpeta_producto(sub)
        if nombre is None:                      # la carpeta es solo el nombre
            nombre, precio, tallas_txt = sub.name.strip(), None, ""
        precio = precio or precio_def
        if not precio:
            print(f"  !! sin precio: {sub.name}  (usa --precio o 'Nombre - 2300')")
            continue

        tallas = tallas_desde_texto(tallas_txt) or tallas_desde_texto(tallas_def) or []
        fotos = sorted([f for f in sub.iterdir()
                        if f.is_file() and f.suffix.lower() in EXTS],
                       key=lambda f: orden_natural(f.name))
        if not fotos:
            print(f"  !! sin fotos: {sub.name}")
            continue

        titulo = bonito(nombre)
        base = slug(titulo)
        galeria = []
        for i, foto in enumerate(fotos):
            sufijo = "portada" if i == 0 else str(i)
            salida = destino_dir / f"{base}-{sufijo}.webp"
            procesar_foto(foto, salida)
            galeria.append(f"img/{carpeta_img}/{salida.name}")

        registro = {
            "name": titulo, "price": precio, "portada": galeria[0],
            "gallery": galeria, "detail": f"p-{base}.html",
            "sizes_raw": "" if tallas else (tallas_txt or ""), "sizes": tallas,
        }
        lista = extra.setdefault(marca, [])
        previo = next((x for x in lista if x["name"] == titulo), None)
        if previo:
            previo.update(registro); actualizados += 1
        else:
            lista.append(registro); nuevos += 1
        t = f"  {len(tallas)} tallas" if tallas else ""
        print(f"  {marca:16} {titulo:40} ${precio:>6,}  {len(galeria)} fotos{t}")

    return nuevos, actualizados


def importar_plano(carpeta, marca, extra):
    """Procesa una carpeta con fotos sueltas y las agrupa por modelo."""
    carpeta_img = CARPETAS.get(marca)
    if not carpeta_img:
        print(f"  !! marca desconocida: '{marca}'")
        return 0, 0

    grupos, problemas = {}, []
    for f in sorted(carpeta.iterdir()):
        if not f.is_file() or f.suffix.lower() not in EXTS:
            continue
        nombre, orden, precio, tallas = leer_nombre_plano(f)
        if not nombre:
            problemas.append(f.name)
            continue
        g = grupos.setdefault(nombre, {"precio": precio, "tallas": tallas, "fotos": []})
        g["fotos"].append((orden, f))

    destino_dir = ROOT / "img" / carpeta_img
    destino_dir.mkdir(parents=True, exist_ok=True)

    nuevos = actualizados = 0
    for nombre, datos in sorted(grupos.items()):
        titulo = bonito(nombre)
        base = slug(titulo)
        fotos = [f for _, f in sorted(datos["fotos"], key=lambda x: x[0])]

        galeria = []
        for i, foto in enumerate(fotos):
            sufijo = "portada" if i == 0 else str(i)
            salida = destino_dir / f"{base}-{sufijo}.webp"
            procesar_foto(foto, salida)
            galeria.append(f"img/{carpeta_img}/{salida.name}")

        registro = {
            "name": titulo,
            "price": datos["precio"],
            "portada": galeria[0],
            "gallery": galeria,
            "detail": f"p-{base}.html",
            "sizes_raw": "",
            "sizes": datos["tallas"],
        }
        lista = extra.setdefault(marca, [])
        previo = next((x for x in lista if x["name"] == titulo), None)
        if previo:
            previo.update(registro); actualizados += 1
        else:
            lista.append(registro); nuevos += 1
        t = f"  {len(datos['tallas'])} tallas" if datos["tallas"] else ""
        print(f"  {marca:16} {titulo:40} ${datos['precio']:>6,}  {len(galeria)} fotos{t}")

    for p in problemas:
        print(f"  !! nombre no entendido, se omite: {p}")
    return nuevos, actualizados


def main():
    # Modo directo:  python tools/importar.py --desde "img/RICK OWENS" --marca "Rick Owens"
    if "--desde" in sys.argv:
        carpeta = Path(sys.argv[sys.argv.index("--desde") + 1])
        if not carpeta.is_absolute():
            carpeta = ROOT / carpeta
        marca = sys.argv[sys.argv.index("--marca") + 1]

        def opcion(nombre, conv=str):
            if nombre in sys.argv:
                return conv(sys.argv[sys.argv.index(nombre) + 1])
            return None

        precio_def = opcion("--precio", lambda v: int(v.replace("$", "").replace(",", "")))
        tallas_def = opcion("--tallas")

        extra = json.loads(EXTRA.read_text(encoding="utf-8")) if EXTRA.exists() else {}
        # Si hay subcarpetas, cada una es un modelo; si no, son fotos sueltas.
        sueltas = [f for f in carpeta.iterdir()
                   if f.is_file() and f.suffix.lower() in EXTS]
        if not sueltas and any(d.is_dir() for d in carpeta.iterdir()):
            n, a = importar_carpetas(carpeta, marca, extra, precio_def, tallas_def)
        else:
            n, a = importar_plano(carpeta, marca, extra)
        EXTRA.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
        print("")
        print(f"Nuevos: {n} | Actualizados: {a}")
        print("")
        print("Ahora corre:  python tools/build.py")
        return

    if not NUEVOS.exists():
        NUEVOS.mkdir()
        print(f"Se creo la carpeta {NUEVOS.name}/ . Mete ahi tus productos y")
        print("vuelve a correr este script. Ver las instrucciones arriba del archivo.")
        return

    extra = {}
    if EXTRA.exists():
        extra = json.loads(EXTRA.read_text(encoding="utf-8"))

    nuevos = actualizados = 0
    problemas = []

    for marca_dir in sorted(p for p in NUEVOS.iterdir() if p.is_dir()):
        marca = marca_dir.name.strip()
        carpeta_img = CARPETAS.get(marca)
        if not carpeta_img:
            problemas.append(
                f"Marca desconocida: '{marca}'. Marcas validas: {', '.join(CARPETAS)}")
            continue

        destino_dir = ROOT / "img" / carpeta_img
        destino_dir.mkdir(parents=True, exist_ok=True)

        for prod_dir in sorted(p for p in marca_dir.iterdir() if p.is_dir()):
            nombre, precio, tallas = leer_carpeta_producto(prod_dir)
            if not nombre:
                problemas.append(
                    f"'{marca}/{prod_dir.name}' no trae precio. Usa: Nombre - 2900")
                continue

            fotos = sorted(f for f in prod_dir.iterdir()
                           if f.is_file() and f.suffix.lower() in EXTS)
            if not fotos:
                problemas.append(f"'{marca}/{prod_dir.name}' no tiene fotos")
                continue

            # La que empiece con "portada" manda; si no, la primera.
            portadas = [f for f in fotos if f.stem.lower().startswith("portada")]
            if portadas:
                fotos = portadas[:1] + [f for f in fotos if f not in portadas[:1]]

            base = slug(f"{marca}-{nombre}")
            galeria = []
            for i, foto in enumerate(fotos):
                sufijo = "portada" if i == 0 else str(i)
                salida = destino_dir / f"{base}-{sufijo}.webp"
                procesar_foto(foto, salida)
                galeria.append(f"img/{carpeta_img}/{salida.name}")

            registro = {
                "name": nombre,
                "price": precio,
                "portada": galeria[0],
                "gallery": galeria,
                "detail": f"p-{base}.html",
                "sizes_raw": tallas,   # vacio = usar las tallas por defecto de la marca
            }
            lista = extra.setdefault(marca, [])
            previo = next((x for x in lista if x["name"] == nombre), None)
            if previo:
                previo.update(registro)
                actualizados += 1
            else:
                lista.append(registro)
                nuevos += 1
            print(f"  {marca:22} {nombre:34} ${precio:>6,}  {len(galeria)} fotos")

    EXTRA.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nNuevos: {nuevos} | Actualizados: {actualizados}")
    if problemas:
        print("\nRevisa esto:")
        for p in problemas:
            print("  !!", p)
    if nuevos or actualizados:
        print("\nAhora corre:  python tools/build.py")


if __name__ == "__main__":
    main()
