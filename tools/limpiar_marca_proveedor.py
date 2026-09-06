#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Borra la marca del proveedor de las fotos y la reemplaza por "Sauce Store".

Algunas fotos del proveedor traen sobre la imagen un texto de comparacion
"batch vs retail": una etiqueta "ZS BATCH (VIA.RM)" (delata al proveedor) y otra
"RETAIL". Este script:
  1. Detecta el texto con OCR (escala de grises + psm 11, muy fiable con texto
     blanco sobre fondo oscuro).
  2. Ubica el bloque "ZS BATCH (VIA.RM)".
  3. Lo rellena con inpainting (OpenCV TELEA) -> el fondo oscuro queda limpio.
  4. Escribe "Sauce Store" en el mismo lugar, con el mismo estilo que "RETAIL"
     (blanco, negrita cursiva, contorno negro).
  5. No toca "RETAIL" para que se siga viendo la comparacion.

    python tools/limpiar_marca_proveedor.py img/Timberland
    python tools/limpiar_marca_proveedor.py img/Timberland/timberland-amarillo-1.webp --dry
    python tools/limpiar_marca_proveedor.py img/Timberland --check   (solo reporta)
"""
import re
import sys
from pathlib import Path

import numpy as np
import cv2
import pytesseract
from PIL import Image, ImageDraw, ImageFont

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ROOT = Path(__file__).resolve().parent.parent

FUENTE = r"C:\Windows\Fonts\arialbi.ttf"   # Arial Bold Italic (igual que "RETAIL")
NUEVO = "Sauce Store"

# tokens del proveedor (tras quitar puntuacion / espacios)
PROV = {"ZS", "BATCH", "VIARM", "VIA", "RM", "ZSBATCH", "BATGH", "BAGH", "BAMTIGH"}


def _norm(t):
    return re.sub(r"[^A-Z]", "", t.upper())


def ocr_boxes(im):
    """[(text, x, y, w, h, conf)] con gris + psm 11 (robusto para texto claro)."""
    g = im.convert("L")
    d = pytesseract.image_to_data(g, config="--psm 11",
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d["text"]):
        t = t.strip()
        try:
            c = int(d["conf"][i])
        except ValueError:
            c = -1
        if t and c > 40:
            out.append((t, d["left"][i], d["top"][i],
                        d["width"][i], d["height"][i], c))
    return out


def analizar(im):
    boxes = ocr_boxes(im)
    prov = []
    retail = None
    for (t, x, y, w, h, c) in boxes:
        n = _norm(t)
        if not n:
            continue
        if "RETAI" in n or "ETAIL" in n:
            retail = (x, y, w, h)
        elif n in PROV or "BATCH" in n or "VIARM" in n or n.startswith("VIA"):
            prov.append((x, y, w, h))
    return prov, retail


def caja_prov(prov, W, H):
    """bbox generoso que cubre 'ZS BATCH' + '(VIA.RM)' (2 renglones)."""
    x0 = min(p[0] for p in prov)
    y0 = min(p[1] for p in prov)
    x1 = max(p[0] + p[2] for p in prov)
    y1 = max(p[1] + p[3] for p in prov)
    lh = max(p[3] for p in prov)          # alto de renglon
    # si OCR solo pillo un renglon, extiende para el segundo
    if (y1 - y0) < lh * 1.6:
        y1 = y0 + int(lh * 2.5)
    # margen
    mx = int(lh * 0.6)
    my = int(lh * 0.5)
    x0 = max(0, x0 - mx); y0 = max(0, y0 - my)
    x1 = min(W, x1 + mx); y1 = min(H, y1 + my)
    return [x0, y0, x1, y1]


def limpiar(path, dry=False, check=False):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    prov, retail = analizar(im)
    if not prov:
        return "sin-marca"
    x0, y0, x1, y1 = caja_prov(prov, W, H)
    if check:
        return "MARCA (%d,%d,%d,%d)%s" % (x0, y0, x1, y1,
                                          "" if retail else "  [sin RETAIL]")
    if dry:
        return "marca (%d,%d,%d,%d)" % (x0, y0, x1, y1)

    arr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    mask = np.zeros((H, W), np.uint8)
    mask[y0:y1, x0:x1] = 255
    arr = cv2.inpaint(arr, mask, 12, cv2.INPAINT_TELEA)
    im = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

    # estilo del texto nuevo: igual alto que "RETAIL" (o que el bloque borrado)
    ref_h = retail[3] if retail else max(p[3] for p in prov)
    fs = max(20, int(round(ref_h / 0.72)))
    try:
        font = ImageFont.truetype(FUENTE, fs)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(im)
    stroke = max(2, fs // 16)
    tb = d.textbbox((0, 0), NUEVO, font=font, stroke_width=stroke)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    # centrar sobre el bloque borrado, sin salir del marco
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    px = min(max(6, cx - tw // 2), W - tw - 6)
    py = min(max(6, cy - th // 2), H - th - 6)
    d.text((px - tb[0], py - tb[1]), NUEVO, font=font, fill=(255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0))

    im.save(path, "WEBP", quality=88, method=6)
    return "limpiada"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    check = "--check" in sys.argv
    obj = ROOT / args[0] if args else None
    if not obj or not obj.exists():
        print("Uso: python tools/limpiar_marca_proveedor.py <carpeta|archivo> [--dry|--check]")
        return
    files = sorted(obj.glob("*.webp")) if obj.is_dir() else [obj]
    n_marca = n_limpia = 0
    for f in files:
        r = limpiar(f, dry, check)
        if r == "sin-marca":
            n_limpia += 1
        else:
            n_marca += 1
            print("  %-44s %s" % (f.name, r))
    print("\ncon marca: %d | sin marca: %d | total: %d" % (n_marca, n_limpia, len(files)))


if __name__ == "__main__":
    main()
