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
    "Jordan 11": "Jordan-11", "Amiri": "Amiri", "Balenciaga": "Balenciaga",
    "Bape": "Bape", "Burberry": "Burberry", "Supreme": "Supreme",
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


def main():
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
