#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convierte las fotos del catalogo a WebP (mucho mas ligeras, se ven igual).

NO borra nada: deja el .webp junto al original. Si algo sale mal, se borran
los .webp y todo queda como estaba.

    python tools/optimize-images.py            # convierte lo que falte
    python tools/optimize-images.py --force    # rehace todos
    python tools/optimize-images.py --stats    # solo reporta, sin convertir
"""
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "img"

MAX_LADO = 1400      # ninguna foto necesita mas para verse bien en pantalla
CALIDAD = 82         # punto donde deja de notarse la diferencia
EXTS = {".png", ".jpg", ".jpeg"}
SALTAR = {"video", "referencias-web"}   # ya optimizadas o no son fotos


def convertibles():
    for f in sorted(IMG.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in EXTS:
            continue
        if any(p in SALTAR for p in f.relative_to(IMG).parts[:-1]):
            continue
        yield f


def mb(n):
    return n / 1048576


def main():
    force = "--force" in sys.argv
    solo_stats = "--stats" in sys.argv

    files = list(convertibles())
    if not files:
        print("No hay imagenes que convertir.")
        return

    peso_orig = sum(f.stat().st_size for f in files)
    print(f"{len(files)} imagenes  |  {mb(peso_orig):.0f} MB en total")

    if solo_stats:
        pendientes = [f for f in files if not f.with_suffix(".webp").exists()]
        print(f"Pendientes de convertir: {len(pendientes)}")
        return

    print(f"Convirtiendo a WebP (max {MAX_LADO}px, calidad {CALIDAD})...\n")

    hechas = saltadas = fallidas = 0
    peso_webp = 0
    t0 = time.time()

    for i, f in enumerate(files, 1):
        out = f.with_suffix(".webp")
        if out.exists() and not force:
            saltadas += 1
            peso_webp += out.stat().st_size
            continue
        try:
            im = Image.open(f)
            # WebP no maneja CMYK ni paletas raras
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "A" in im.mode or im.mode == "P" else "RGB")
            im.thumbnail((MAX_LADO, MAX_LADO), Image.LANCZOS)
            im.save(out, "WEBP", quality=CALIDAD, method=5)
            peso_webp += out.stat().st_size
            hechas += 1
        except Exception as e:
            print(f"  !! {f.relative_to(ROOT)}: {e}")
            fallidas += 1

        if i % 200 == 0 or i == len(files):
            print(f"  {i}/{len(files)}  ({time.time()-t0:.0f}s)")

    print(f"\nConvertidas: {hechas} | Ya existian: {saltadas} | Fallidas: {fallidas}")
    if peso_webp:
        ahorro = 100 * (1 - peso_webp / peso_orig)
        print(f"Antes:  {mb(peso_orig):>7.0f} MB")
        print(f"Ahora:  {mb(peso_webp):>7.0f} MB  ({ahorro:.0f}% menos)")
        print("\nLos originales siguen ahi. Corre 'python tools/build.py' para que")
        print("las paginas empiecen a usar los .webp")


if __name__ == "__main__":
    main()
