# -*- coding: utf-8 -*-
"""
Genera la imagen vertical 9:16 (1080x1920) para historias de Instagram / Facebook.

Uso:
    python tools/social_story.py --id aj1travisreversemocha --deal --out story.jpg
    python tools/social_story.py --id p-lv-cardigan --out story.jpg

--deal  -> version "El producto del dia" (precio tachado + 10% de descuento).
Sin --deal -> version normal (nombre + precio).

Instagram solo acepta JPEG, por eso la salida es .jpg (las fotos del sitio son WebP).
Todo el texto importante queda dentro de la zona segura de historias (el borde
superior e inferior de la pantalla los tapa la interfaz de IG).
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920

BG = (14, 14, 14)
IVORY = (244, 237, 221)
DIM = (150, 146, 138)
ACCENT = (232, 163, 61)
INK = (14, 14, 14)

SITE = "sauce-store-86z.pages.dev"
OFF = 0.10  # mismo descuento que la prenda del dia de la web

FONT_DIR = Path("C:/Windows/Fonts")
FONT_FILES = {
    "head": ["impact.ttf", "ariblk.ttf", "arialbd.ttf"],
    "body": ["arialbd.ttf", "bahnschrift.ttf", "arial.ttf"],
}


def font(kind, size):
    for name in FONT_FILES[kind]:
        p = FONT_DIR / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def text_w(d, text, f, spacing=0):
    if not text:
        return 0
    return int(d.textlength(text, font=f)) + spacing * (len(text) - 1)


def draw_spaced(d, x, y, text, f, fill, spacing=0):
    """Texto con separacion entre letras. Devuelve el ancho dibujado."""
    if spacing == 0:
        d.text((x, y), text, font=f, fill=fill)
        return int(d.textlength(text, font=f))
    cx = x
    for ch in text:
        d.text((cx, y), ch, font=f, fill=fill)
        cx += int(d.textlength(ch, font=f)) + spacing
    return cx - x - spacing


def draw_center(d, y, text, f, fill, spacing=0, cx=W // 2):
    w = text_w(d, text, f, spacing)
    draw_spaced(d, cx - w // 2, y, text, f, fill, spacing)
    return w


def wrap(d, text, f, max_w, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if text_w(d, test, f) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while text_w(d, lines[-1] + "...", f) > max_w and len(lines[-1]) > 1:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "..."
    return lines


def money(n):
    return "${:,} MXN".format(int(round(n)))


def star(d, cx, cy, r, fill):
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=fill)


def base_price(prod):
    """Precio de referencia: si hay opciones con precio propio, el mas bajo."""
    opts = prod.get("options") or []
    if isinstance(opts, dict):
        opts = [opts]
    lows = [c["price"] for g in opts for c in g.get("choices", [])
            if isinstance(c.get("price"), (int, float))]
    return min(lows) if lows else prod["price"]


def photo_card(path, w, h, radius=40):
    """Foto dentro de una tarjeta.
    - Si la proporcion de la foto se parece a la de la tarjeta: se recorta para llenarla.
    - Si es muy distinta (p.ej. prenda colgada, vertical): se muestra completa sobre
      una copia borrosa y oscura de la misma foto, para que no queden franjas lisas."""
    from PIL import ImageFilter, ImageEnhance
    ph = Image.open(path).convert("RGB")
    pw, pht = ph.size
    ratio = (pw / pht) / (w / h)
    if 0.75 <= ratio <= 1.33:
        scale = max(w / pw, h / pht)
        nw, nh = int(pw * scale) + 1, int(pht * scale) + 1
        big = ph.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - w) // 2, (nh - h) // 2
        card = big.crop((left, top, left + w, top + h))
    else:
        scale = max(w / pw, h / pht)
        bg = ph.resize((int(pw * scale) + 1, int(pht * scale) + 1), Image.BILINEAR)
        left, top = (bg.width - w) // 2, (bg.height - h) // 2
        bg = bg.crop((left, top, left + w, top + h)).filter(ImageFilter.GaussianBlur(38))
        card = ImageEnhance.Brightness(bg).enhance(0.38)
        scale = min(w / pw, h / pht)
        nw, nh = int(pw * scale), int(pht * scale)
        card.paste(ph.resize((nw, nh), Image.LANCZOS), ((w - nw) // 2, (h - nh) // 2))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    return card, mask


def make_story(prod, deal, out):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- marca (debajo de la barra de IG) ---
    f_mark = font("head", 50)
    mark = "SAUCE STORE"
    mw = text_w(d, mark, f_mark, 8)
    x0 = W // 2 - (mw + 60) // 2
    draw_spaced(d, x0, 258, mark, f_mark, IVORY, 8)
    star(d, x0 + mw + 38, 285, 17, ACCENT)

    # --- nombre: se parte primero para saber cuanto espacio queda a la foto ---
    f_name = font("head", 80)
    lines = wrap(d, prod["name"].upper(), f_name, 940, 2)

    # --- foto (si el nombre cabe en 1 linea, la foto crece 90px) ---
    card_w, card_y = 960, 345
    card_h = 760 + (2 - len(lines)) * 90
    card, mask = photo_card(ROOT / prod["img"], card_w, card_h)
    img.paste(card, ((W - card_w) // 2, card_y), mask)

    if deal:
        # etiqueta arriba a la izquierda
        f_tag = font("body", 30)
        tag = "EL PRODUCTO DEL DÍA"
        tw = text_w(d, tag, f_tag, 3)
        bx, by = 90, card_y + 34
        d.rounded_rectangle((bx, by, bx + tw + 56, by + 62), radius=31, fill=ACCENT)
        draw_spaced(d, bx + 28, by + 14, tag, f_tag, INK, 3)
        # circulo -10% arriba a la derecha
        cx, cy, r = W - 160, card_y + 105, 78
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK, outline=ACCENT, width=6)
        f_pct = font("head", 62)
        pct = "-%d%%" % int(OFF * 100)
        pw = int(d.textlength(pct, font=f_pct))
        d.text((cx - pw // 2, cy - 38), pct, font=f_pct, fill=ACCENT)

    # --- categoria ---
    f_cat = font("body", 32)
    cat_y = card_y + card_h + 37
    draw_center(d, cat_y, prod["cat"].upper(), f_cat, DIM, spacing=6)

    # --- nombre (hasta 2 lineas) ---
    y = cat_y + 50
    for ln in lines:
        draw_center(d, y, ln, f_name, IVORY)
        y += 90
    y_price = 1192 + 90 * 2 + 12   # constante: la foto absorbe la diferencia

    # --- precio ---
    price = base_price(prod)
    if deal:
        new = round(price * (1 - OFF))
        f_old = font("body", 48)
        f_new = font("head", 112)
        old_t, new_t = money(price), money(new)
        ow, nw_ = text_w(d, old_t, f_old), text_w(d, new_t, f_new)
        gap = 30
        x = W // 2 - (ow + gap + nw_) // 2
        oy = y_price + 50
        d.text((x, oy), old_t, font=f_old, fill=DIM)
        d.line((x - 4, oy + 30, x + ow + 4, oy + 30), fill=DIM, width=4)
        d.text((x + ow + gap, y_price), new_t, font=f_new, fill=ACCENT)
        draw_center(d, y_price + 128, "SOLO HOY  -  CAMBIA A LAS 12:00 AM",
                    font("body", 28), DIM, spacing=3)
    else:
        f_new = font("head", 112)
        draw_center(d, y_price, money(price), f_new, ACCENT)

    # --- llamado a la accion ---
    f_cta = font("body", 33)
    cta = "CONSÍGUELO EN  " + SITE
    cw = text_w(d, cta, f_cta, 2)
    pad = 46
    bx0 = W // 2 - (cw + pad * 2) // 2
    by0 = 1568
    d.rounded_rectangle((bx0, by0, bx0 + cw + pad * 2, by0 + 76), radius=38,
                        outline=ACCENT, width=4)
    draw_spaced(d, bx0 + pad, by0 + 20, cta, f_cta, IVORY, 2)

    img.save(out, "JPEG", quality=92, optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="id del producto en productos.json")
    ap.add_argument("--deal", action="store_true", help="version producto del dia")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    prods = json.loads((ROOT / "productos.json").read_text(encoding="utf-8"))
    if a.id not in prods:
        sys.exit("No existe el producto: %s" % a.id)
    make_story(prods[a.id], a.deal, a.out)
    print("OK ->", a.out)


if __name__ == "__main__":
    main()
