# -*- coding: utf-8 -*-
"""
Estilos de historia (1080x1920) para IG / FB. Reusa los helpers de social_story.py.

Uso:
    python tools/social_styles.py --id p-hoodie-dior-blanca --out-dir salida/

Genera un JPG por estilo: clasico, dia, completa, editorial, collage, ticket, oferta.
Todo el texto importante queda dentro de la zona segura de historias (~y 270 a 1650).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_story as ss  # noqa: E402

ROOT = ss.ROOT
W, H = ss.W, ss.H
BG, IVORY, DIM, ACCENT, INK = ss.BG, ss.IVORY, ss.DIM, ss.ACCENT, ss.INK
CREAM = (244, 237, 221)
CREAM_DARK = (231, 222, 200)
FONT_DIR = ss.FONT_DIR


# ----------------------------------------------------------------- helpers
def mono(size, bold=True):
    p = FONT_DIR / ("courbd.ttf" if bold else "cour.ttf")
    return ImageFont.truetype(str(p), size) if p.exists() else ss.font("body", size)


def draw_box(d, cx, y_top, text, f, fill, spacing=0):
    """Centra por el recuadro real del texto: y_top es donde empieza a verse la tinta."""
    if spacing:
        w = ss.text_w(d, text, f, spacing)
        l, t, r, b = d.textbbox((0, 0), text[0], font=f)
        x = cx - w // 2
        ss.draw_spaced(d, x, y_top - t, text, f, fill, spacing)
        return y_top + (b - t)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text((cx - (r - l) // 2 - l, y_top - t), text, font=f, fill=fill)
    return y_top + (b - t)


def cover(img, w, h, bias_y=0.5):
    iw, ih = img.size
    sc = max(w / iw, h / ih)
    nw, nh = int(iw * sc) + 1, int(ih * sc) + 1
    big = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = int((nh - h) * bias_y)
    return big.crop((left, top, left + w, top + h))


def rounded(img, radius):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(m)
    return out


def shadow_paste(base, rgba, xy, blur=28, offset=(0, 18), alpha=110):
    sh = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    sh.putalpha(rgba.split()[3].point(lambda v: int(v * alpha / 255)))
    pad = blur * 3
    big = Image.new("RGBA", (rgba.width + pad * 2, rgba.height + pad * 2), (0, 0, 0, 0))
    big.paste(sh, (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur))
    base.paste(big, (xy[0] - pad + offset[0], xy[1] - pad + offset[1]), big)
    base.paste(rgba, xy, rgba)


def lum(img):
    g = img.convert("L").resize((1, 1), Image.BILINEAR)
    return g.getpixel((0, 0))


def wordmark(d, y, color, star_color=ACCENT):
    f = ss.font("head", 50)
    txt = "SAUCE STORE"
    mw = ss.text_w(d, txt, f, 8)
    x0 = W // 2 - (mw + 60) // 2
    ss.draw_spaced(d, x0, y, txt, f, color, 8)
    ss.star(d, x0 + mw + 38, y + 27, 17, star_color)


def cta(d, y, dark_bg=True, label="CONSÍGUELO EN"):
    f = ss.font("body", 33)
    txt = "%s  %s" % (label, ss.SITE)
    cw = ss.text_w(d, txt, f, 2)
    pad = 46
    x0 = W // 2 - (cw + pad * 2) // 2
    if dark_bg:
        d.rounded_rectangle((x0, y, x0 + cw + pad * 2, y + 76), radius=38, outline=ACCENT, width=4)
        ss.draw_spaced(d, x0 + pad, y + 20, txt, f, IVORY, 2)
    else:
        d.rounded_rectangle((x0, y, x0 + cw + pad * 2, y + 76), radius=38, fill=INK)
        ss.draw_spaced(d, x0 + pad, y + 20, txt, f, CREAM, 2)


_CATS = None


def load(pid):
    global _CATS
    if _CATS is None:
        _CATS = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    cats = _CATS
    for c in cats:
        for p in c["products"]:
            if p["id"] == pid:
                gal = [g for g in p["gallery"]]
                prod = {"name": p["name"], "cat": c["title"], "price": p["price_num"],
                        "img": p["portada"] or gal[0], "options": p.get("options"),
                        "sizes": p.get("size_options") or []}
                return prod, gal
    sys.exit("No existe el producto: %s" % pid)


def photo(path):
    """Foto del producto. Si no esta en disco (en el servidor solo se baja lo necesario del
    repo), se trae del sitio publicado."""
    local = ROOT / path
    if local.exists():
        return Image.open(local).convert("RGB")
    import io
    import time
    import urllib.parse
    import urllib.request
    url = "https://%s/%s" % (ss.SITE, urllib.parse.quote(path))
    for intento in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SauceStoreBot)"})
            return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=40).read())).convert("RGB")
        except Exception:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))


# ----------------------------------------------------------------- estilos
def tallas_txt(sizes, prefijo="TALLAS  ", sep="  ·  "):
    """Texto de tallas segun el producto: S·M·L·XL, 24 A 29, UNITALLA..."""
    sizes = [str(x) for x in (sizes or [])]
    if not sizes:
        return ""
    # Tenis con formato "24.5 MX (39 EU)": en la historia solo "24.5 A 30 MX"
    import re as _re
    mx = [_re.match(r"^\s*([\d.]+)\s*MX", x, _re.I) for x in sizes]
    if all(mx):
        nums = [m.group(1) for m in mx]
        return "%s%s A %s MX" % (prefijo, nums[0], nums[-1]) if len(nums) > 1 else "%s%s MX" % (prefijo, nums[0])
    if len(sizes) == 1:
        return sizes[0].upper() if sizes[0].lower() == "unitalla" else prefijo + sizes[0]
    if len(sizes) > 7:
        return "%s%s A %s" % (prefijo, sizes[0], sizes[-1])
    return prefijo + sep.join(sizes)


def st_clasico(prod, gal, out, deal=False):
    ss.make_story(prod, deal, out)


IG_HANDLE = "sauceestore"
FOOT_TXT = "Encarga con el 50% y liquida en la entrega"


def fondo_historia(ph, limite=None):
    """Fondo a pantalla completa. Devuelve (imagen, modo). La foto SIEMPRE se muestra
    completa, arriba del bloque de texto, sobre una copia borrosa y oscura de ella misma:
    recortarla (o dejarla debajo del texto) tapaba el producto en prendas y lentes.
    - "contain": foto horizontal / cuadrada / 3:4 -> ancho completo, hasta 880 px de alto.
    - "alto": foto vertical (ratio <= 0.70) -> se achica hasta caber entre la parte de arriba
      y `limite` (donde arranca el degradado del texto)."""
    r = ph.width / ph.height
    bgc = cover(ph, W, H, 0.5).filter(ImageFilter.GaussianBlur(40))
    bgc = ImageEnhance.Brightness(bgc).enhance(0.42)
    if r <= 0.70:
        top = 120
        fh = max(400, min(1500, (limite or 1050) + 25 - top))
        fw = int(fh * r)
        if fw > W:
            fw, fh = W, int(W / r)
        bgc.paste(ph.resize((fw, fh), Image.LANCZOS), ((W - fw) // 2, top))
        return bgc, "alto"
    fw, fh = W, int(W / r)
    if fh > 880:
        fw, fh = int(880 * r), 880
    bgc.paste(ph.resize((fw, fh), Image.LANCZOS), ((W - fw) // 2, 650 - fh // 2))
    return bgc, "contain"


def ig_line(d, y, color=IVORY):
    """Icono de Instagram dibujado + @usuario, centrado."""
    f = ss.font("body", 34)
    txt = "@" + IG_HANDLE
    tw = ss.text_w(d, txt, f, 2)
    ic = 38
    x0 = W // 2 - (ic + 14 + tw) // 2
    d.rounded_rectangle((x0, y, x0 + ic, y + ic), radius=11, outline=ACCENT, width=4)
    d.ellipse((x0 + 9, y + 9, x0 + ic - 9, y + ic - 9), outline=ACCENT, width=3)
    d.ellipse((x0 + ic - 13, y + 7, x0 + ic - 8, y + 12), fill=ACCENT)
    ss.draw_spaced(d, x0 + ic + 14, y + 1, txt, f, color, 2)


def st_completa(prod, gal, out, deal=False, off=0.10):
    """Foto a pantalla completa, texto sobre degradado.
    Con deal=True: version "producto del dia" (precio tachado + descuento)."""
    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    def alto(txt, f):
        l, t, r, b = scratch.textbbox((0, 0), txt, font=f)
        return b - t

    # --- medidas (el bloque se acomoda de abajo hacia arriba: nunca se encima) ---
    nombre = prod["name"].upper()
    for tam in (96, 84, 74, 66, 58):
        f_name = ss.font("head", tam)
        lines = ss.wrap(scratch, nombre, f_name, 940, 3)
        if len(lines) <= (1 if tam == 96 else 2):
            break
    lines = ss.wrap(scratch, nombre, f_name, 940, 2)
    lh = [alto(ln, f_name) for ln in lines]
    name_h = sum(lh) + 16 * (len(lines) - 1)
    f_price = ss.font("head", 112)
    f_old = ss.font("body", 44)
    f_tal = ss.font("body", 30)
    price_txt = ss.money(round(prod["price"] * (1 - off)) if deal else prod["price"])
    price_h = alto(price_txt, f_price)
    old_h = alto(ss.money(prod["price"]), f_old) if deal else 0
    tallas = tallas_txt(prod.get("sizes"))
    tal_h = alto(tallas, f_tal) if tallas else 0

    y_cta = 1500
    tal_top = y_cta - 30 - tal_h if tallas else y_cta - 8
    price_top = (tal_top - 24 if tallas else tal_top - 14) - price_h
    stack_top = price_top - (old_h + 14 if deal else 0)
    name_top = stack_top - 36 - name_h
    tag_top = name_top - 30 - 62

    # --- fondo: foto + degradado que arranca arriba del bloque de texto ---
    # el degradado arranca justo arriba de la etiqueta; la foto no pasa de ahi
    largo = 120
    y0 = max(0, tag_top - 55)
    bg, modo = fondo_historia(photo(prod["img"]), y0)
    mask = Image.new("L", (W, H), 0)
    ramp = Image.linear_gradient("L").resize((W, largo)).point(lambda v: int(v * 242 / 255))
    mask.paste(ramp, (0, y0))
    mask.paste(242, (0, y0 + largo, W, H))
    bg = Image.composite(Image.new("RGB", (W, H), (10, 10, 10)), bg, mask).convert("RGBA")
    pill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle((300, 238, 780, 318), radius=40, fill=(14, 14, 14, 215))
    bg = Image.alpha_composite(bg, pill).convert("RGB")
    d = ImageDraw.Draw(bg)
    wordmark(d, 258, IVORY)

    # --- etiqueta ---
    f_tag = ss.font("body", 30)
    tag = "EL PRODUCTO DEL DÍA  ·  -%d%%" % int(off * 100) if deal else "DISPONIBLE POR ENCARGO"
    tw = ss.text_w(d, tag, f_tag, 3)
    d.rounded_rectangle((90, tag_top, 90 + tw + 56, tag_top + 62), radius=31, fill=ACCENT)
    ss.draw_spaced(d, 118, tag_top + 14, tag, f_tag, INK, 3)

    # --- nombre / precio / tallas ---
    y = name_top
    for ln in lines:
        y = draw_box(d, W // 2, y, ln, f_name, IVORY) + 16
    if deal:
        old_t = ss.money(prod["price"])
        ow = ss.text_w(d, old_t, f_old)
        oy = stack_top
        yb = draw_box(d, W // 2, oy, old_t, f_old, DIM)
        d.line((W // 2 - ow // 2 - 4, (oy + yb) // 2 + 2, W // 2 + ow // 2 + 4, (oy + yb) // 2 + 2),
               fill=DIM, width=4)
    draw_box(d, W // 2, price_top, price_txt, f_price, ACCENT)
    if tallas:
        draw_box(d, W // 2, tal_top, tallas, f_tal, IVORY, 4)

    # --- llamado a la accion + instagram + letra chica ---
    cta(d, y_cta)
    ig_line(d, y_cta + 92)
    draw_box(d, W // 2, y_cta + 92 + 38 + 20, FOOT_TXT, ss.font("body", 26), (196, 191, 180), 2)
    bg.save(out, "JPEG", quality=92, optimize=True)


def arch_mask(w, h):
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    md.ellipse((0, 0, w, w), fill=255)
    md.rectangle((0, w // 2, w, h), fill=255)
    return m


def st_editorial(prod, gal, out):
    """Fondo crema, foto en arco, sticker de precio y la mascota."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # palabra gigante de fondo
    brand = prod["name"].split()[1].upper() if len(prod["name"].split()) > 1 else "SAUCE"
    big = ss.font("head", 470)
    draw_box(d, W // 2, 330, brand, big, CREAM_DARK)
    wordmark(d, 258, INK)

    aw, ah = 780, 920
    ph = cover(photo(prod["img"]), aw, ah, 0.35)
    ph.putalpha(arch_mask(aw, ah))
    ax, ay = (W - aw) // 2, 345
    shadow_paste(img, ph, (ax, ay), blur=30, offset=(0, 20), alpha=90)
    d = ImageDraw.Draw(img)

    # nombre
    f_name = ss.font("head", 92)
    lines = ss.wrap(d, prod["name"].upper(), f_name, 940, 2)
    y = 1395
    for ln in lines:
        y = draw_box(d, W // 2, y, ln, f_name, INK) + 14
    draw_box(d, W // 2, y + 6, tallas_txt(prod.get("sizes"), prefijo=""), ss.font("body", 32), (110, 104, 92), 6)

    # sticker de precio
    cx, cy, r = 858, 1215, 118
    st = Image.new("RGBA", (r * 2 + 10, r * 2 + 10), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.ellipse((5, 5, r * 2 + 5, r * 2 + 5), fill=ACCENT)
    sd.ellipse((20, 20, r * 2 - 10, r * 2 - 10), outline=INK, width=4)
    pf = ss.font("head", 66)
    ptxt = "${:,}".format(prod["price"])
    pw = int(sd.textlength(ptxt, font=pf))
    sd.text((r + 5 - pw // 2, r - 46), ptxt, font=pf, fill=INK)
    mf = ss.font("body", 28)
    mw = int(sd.textlength("MXN", font=mf))
    sd.text((r + 5 - mw // 2, r + 32), "MXN", font=mf, fill=INK)
    st = st.rotate(-8, resample=Image.BICUBIC)
    shadow_paste(img, st, (cx - r, cy - r), blur=12, offset=(0, 8), alpha=90)

    # mascota
    try:
        m = Image.open(ROOT / "img" / "mascota-320.webp").convert("RGBA")
        m.thumbnail((250, 250))
        shadow_paste(img, m, (46, 1030), blur=10, offset=(0, 6), alpha=70)
    except Exception:
        pass
    d = ImageDraw.Draw(img)
    cta(d, 1568, dark_bg=False)
    img.save(out, "JPEG", quality=92, optimize=True)


def st_collage(prod, gal, out):
    """2x2 de detalles de calidad."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    wordmark(d, 258, IVORY)
    draw_box(d, W // 2, 345, "CALIDAD QUE SE VE", ss.font("head", 84), IVORY, 3)

    detalles = [(3, "CAPUCHA"), (4, "BORDADO"), (5, "ZIPPER"), (6, "CORDONES")]
    t, gap = 430, 20
    x0 = (W - (t * 2 + gap)) // 2
    y0 = 470
    f_l = ss.font("body", 26)
    for i, (idx, label) in enumerate(detalles):
        if idx >= len(gal):
            continue
        tile = rounded(cover(photo(gal[idx]), t, t), 28)
        x = x0 + (i % 2) * (t + gap)
        y = y0 + (i // 2) * (t + gap)
        img.paste(tile, (x, y), tile)
        d = ImageDraw.Draw(img)
        lw = ss.text_w(d, label, f_l, 3)
        d.rounded_rectangle((x + 16, y + t - 62, x + 16 + lw + 36, y + t - 18), radius=22, fill=INK)
        ss.draw_spaced(d, x + 34, y + t - 53, label, f_l, ACCENT, 3)

    yb = y0 + t * 2 + gap + 28
    f_name = ss.font("head", 74)
    yb = draw_box(d, W // 2, yb, prod["name"].upper(), f_name, IVORY) + 22
    draw_box(d, W // 2, yb, ss.money(prod["price"]), ss.font("head", 96), ACCENT)
    cta(d, 1568)
    img.save(out, "JPEG", quality=92, optimize=True)


def st_ticket(prod, gal, out):
    """Ticket de pedido (el mismo concepto del sitio), ligeramente chueco."""
    cw, chh = 840, 1245
    card = Image.new("RGBA", (cw, chh), CREAM + (255,))
    d = ImageDraw.Draw(card)
    # bordes de papel (dientes arriba y abajo)
    step = 28
    for x in range(0, cw, step):
        d.polygon([(x, 0), (x + step // 2, 22), (x + step, 0)], fill=(0, 0, 0, 0))
        d.polygon([(x, chh), (x + step // 2, chh - 22), (x + step, chh)], fill=(0, 0, 0, 0))
    m = Image.new("L", (cw, chh), 255)
    md = ImageDraw.Draw(m)
    for x in range(0, cw, step):
        md.polygon([(x, 0), (x + step // 2, 22), (x + step, 0)], fill=0)
        md.polygon([(x, chh), (x + step // 2, chh - 22), (x + step, chh)], fill=0)
    card.putalpha(m)

    def dotted(y):
        for x in range(50, cw - 50, 14):
            d.rectangle((x, y, x + 6, y + 3), fill=INK)

    d.text((0, 0), "", font=ss.font("head", 10))
    ft = ss.font("head", 70)
    tw_ = ss.text_w(d, "SAUCE STORE", ft, 6)
    draw_box(d, cw // 2 - 28, 58, "SAUCE STORE", ft, INK, 6)
    ss.star(d, cw // 2 - 28 + tw_ // 2 + 44, 93, 20, ACCENT)
    draw_box(d, cw // 2, 150, "TICKET DE PEDIDO", mono(30), INK, 5)
    dotted(205)

    th = rounded(cover(photo(prod["img"]), 360, 360, 0.3), 14)
    card.paste(th, ((cw - 360) // 2, 232), th)

    y = 622
    f_it = mono(38)
    for ln in ss.wrap(d, "1x " + prod["name"].upper(), f_it, cw - 100, 2):
        d.text((50, y), ln, font=f_it, fill=INK)
        y += 46
    d.text((50, y + 6), tallas_txt(prod.get("sizes"), prefijo="TALLAS: ", sep=" ").replace("  ", " "), font=mono(30, False), fill=(90, 84, 72))
    y += 62
    dotted(y)
    y += 24

    def fila(izq, der, yy, f, col=INK):
        d.text((50, yy), izq, font=f, fill=col)
        w = int(d.textlength(der, font=f))
        d.text((cw - 50 - w, yy), der, font=f, fill=col)

    f_r = mono(32)
    fila("PRECIO", ss.money(prod["price"]), y, f_r)
    fila("APARTAS CON 50%", ss.money(prod["price"] / 2), y + 52, f_r)
    fila("ENVIO (LIQUIDANDO)", "GRATIS", y + 104, f_r)
    y += 168
    dotted(y)
    y += 22
    fila("TOTAL", ss.money(prod["price"]), y, mono(46))
    y += 84

    # codigo de barras (determinista por nombre)
    seed = hashlib.md5(prod["name"].encode()).digest()
    x = 130
    i = 0
    while x < cw - 130:
        wbar = 2 + seed[i % 16] % 5
        if i % 2 == 0:
            d.rectangle((x, y, x + wbar, y + 78), fill=INK)
        x += wbar + 2
        i += 1
    draw_box(d, cw // 2, y + 96, "GENERA TU TICKET EN", mono(26, False), (90, 84, 72), 3)
    draw_box(d, cw // 2, y + 134, ss.SITE, mono(30), INK)

    card = card.rotate(2.6, resample=Image.BICUBIC, expand=True)
    img = Image.new("RGB", (W, H), (24, 24, 24))
    # textura sutil de puntos
    dd = ImageDraw.Draw(img)
    for gx in range(0, W, 54):
        for gy in range(0, H, 54):
            dd.ellipse((gx, gy, gx + 3, gy + 3), fill=(38, 38, 38))
    wordmark(dd, 258, IVORY)
    shadow_paste(img, card, ((W - card.width) // 2, 345), blur=26, offset=(0, 22), alpha=140)
    dd = ImageDraw.Draw(img)
    draw_box(dd, W // 2, 1640 - 6, "SIN PAGOS EN LA WEB · TU PEDIDO POR TICKET", ss.font("body", 24), DIM, 3)
    img.save(out, "JPEG", quality=92, optimize=True)


def st_oferta(prod, gal, out, off=0.10):
    """Oferta del dia: fondo mostaza, descuento gigante, foto tipo polaroid."""
    img = Image.new("RGB", (W, H), ACCENT)
    d = ImageDraw.Draw(img)
    wordmark(d, 258, INK, star_color=INK)
    pct = "-%d%%" % int(off * 100)
    y = draw_box(d, W // 2, 335, pct, ss.font("head", 360), INK)
    draw_box(d, W // 2, y + 18, "SOLO HOY", ss.font("head", 84), INK, 10)

    cw_, ch_ = 520, 640
    border = 16
    ph = cover(photo(prod["img"]), cw_ - border * 2, ch_ - border * 2 - 40, 0.35)
    card = Image.new("RGBA", (cw_, ch_), (255, 255, 255, 255))
    card.paste(ph, (border, border))
    card = rounded(card.convert("RGB"), 14)
    card = card.rotate(-6, resample=Image.BICUBIC, expand=True)
    shadow_paste(img, card, ((W - card.width) // 2 - 40, 760), blur=24, offset=(0, 20), alpha=120)

    # cinta con el nombre
    d = ImageDraw.Draw(img)
    f_n = ss.font("body", 34)
    nm = prod["name"].upper()
    nw = ss.text_w(d, nm, f_n, 3)
    d.rounded_rectangle((70, 960, 70 + nw + 56, 1026), radius=33, fill=INK)
    ss.draw_spaced(d, 98, 975, nm, f_n, ACCENT, 3)

    # sticker de precio nuevo
    new = round(prod["price"] * (1 - off))
    cx, cy, r = 842, 1330, 150
    st = Image.new("RGBA", (r * 2 + 10, r * 2 + 10), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.ellipse((5, 5, r * 2 + 5, r * 2 + 5), fill=INK)
    of = ss.font("body", 32)
    otxt = "${:,}".format(prod["price"])
    ow = int(sd.textlength(otxt, font=of))
    sd.text((r + 5 - ow // 2, r - 78), otxt, font=of, fill=DIM)
    sd.line((r + 5 - ow // 2 - 4, r - 60, r + 5 + ow // 2 + 4, r - 60), fill=DIM, width=3)
    nf = ss.font("head", 88)
    ntxt = "${:,}".format(new)
    nw2 = int(sd.textlength(ntxt, font=nf))
    sd.text((r + 5 - nw2 // 2, r - 38), ntxt, font=nf, fill=ACCENT)
    mf = ss.font("body", 28)
    mw = int(sd.textlength("MXN", font=mf))
    sd.text((r + 5 - mw // 2, r + 72), "MXN", font=mf, fill=IVORY)
    st = st.rotate(7, resample=Image.BICUBIC)
    shadow_paste(img, st, (cx - r, cy - r), blur=14, offset=(0, 10), alpha=110)

    d = ImageDraw.Draw(img)
    draw_box(d, W // 2, 1500, "CAMBIA A LAS 12:00 AM", ss.font("body", 28), INK, 4)
    cta(d, 1568, dark_bg=False)
    img.save(out, "JPEG", quality=92, optimize=True)


ESTILOS = ["clasico", "dia", "completa", "editorial", "collage", "ticket", "oferta", "completa_dia"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--estilo", default="todos", help="uno de: %s" % ", ".join(ESTILOS))
    a = ap.parse_args()
    prod, gal = load(a.id)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fns = {
        "clasico": lambda o: st_clasico(prod, gal, o, False),
        "dia": lambda o: st_clasico(prod, gal, o, True),
        "completa": lambda o: st_completa(prod, gal, o),
        "editorial": lambda o: st_editorial(prod, gal, o),
        "collage": lambda o: st_collage(prod, gal, o),
        "ticket": lambda o: st_ticket(prod, gal, o),
        "oferta": lambda o: st_oferta(prod, gal, o),
        "completa_dia": lambda o: st_completa(prod, gal, o, True),
    }
    for i, nombre in enumerate(ESTILOS, 1):
        if a.estilo not in ("todos", nombre):
            continue
        f = str(out / ("%d_%s.jpg" % (i, nombre)))
        fns[nombre](f)
        print("OK ->", f)


if __name__ == "__main__":
    main()
