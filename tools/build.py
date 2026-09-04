#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del catalogo Sauce Store.

Lee los HTML de categoria existentes (fuente de verdad de nombre/precio/tallas/
portada) y las galerias de las paginas de detalle, arma catalog.json y regenera:
  - index.html
  - un HTML por categoria de la whitelist
  - un HTML de detalle por producto

Solo stdlib. Ejecutar desde la carpeta Sauce-Store/ o desde cualquier lado:
    python tools/build.py
"""
import json
import re
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_source"   # copia pristina de los HTML originales (fuente de verdad)
WA = "https://chat.whatsapp.com/GamukaM3CgJKFZLSQMU4uy"
IG = "https://www.instagram.com/sauceestore"

# ----------------------------------------------------------------------------
# Whitelist de categorias: slug de archivo -> (titulo, grupo de menu, carpeta img)
# ----------------------------------------------------------------------------
CATEGORIES = [
    ("Jordan1.html",          "Jordan 1",              "tenis",      "img/Jordan-1"),
    ("jordan3.html",          "Jordan 3",              "tenis",      "img/Jordan-3"),
    ("jordan4.html",          "Jordan 4",              "tenis",      "img/Jordan-4"),
    ("jordan5.html",          "Jordan 5",              "tenis",      "img/Jordan-5"),
    ("jordan6.html",          "Jordan 6",              "tenis",      "img/Jordan-6"),
    ("jordan10.html",         "Jordan 10",             "tenis",      "img/Jordan-10"),
    ("jordan11.html",         "Jordan 11",             "tenis",      "img/Jordan-11"),
    ("Amiri.html",            "Amiri",                 "ropa",       "img/Amiri"),
    ("Balenciaga.html",       "Balenciaga",            "ropa",       "img/Balenciaga"),
    ("Bape.html",             "Bape",                  "ropa",       "img/Bape"),
    ("Burberry.html",         "Burberry",              "ropa",       "img/Burberry"),
    ("Supreme.html",          "Supreme",               "ropa",       "img/Supreme"),
    ("ChromeHeartsRopa.html", "Chrome Hearts",         "ropa",       "img/Chrome-Hearts-Ropa"),
    ("ChromeHearts.html",     "Chrome Hearts Cadenas", "accesorios", "img/Chrome-Hearts-Cadenas"),
    ("Stock.html",            "Stock",                 "stock",      "img/Stock"),
]

MENU_LABELS = {"tenis": "Tenis", "ropa": "Ropa", "accesorios": "Accesorios", "stock": "Stock"}

# Alias/variantes por categoria para que el buscador tolere errores de escritura
BRAND_ALIASES = {
    "Jordan 1": "jordan jordans jordanes air jordan aj1 aj 1 jordan1 chandal tenis",
    "Jordan 3": "jordan jordans jordanes air jordan aj3 aj 3 jordan3 tenis",
    "Jordan 4": "jordan jordans jordanes air jordan aj4 aj 4 jordan4 tenis",
    "Jordan 5": "jordan jordans jordanes air jordan aj5 aj 5 jordan5 tenis",
    "Jordan 6": "jordan jordans jordanes air jordan aj6 aj 6 jordan6 tenis",
    "Jordan 10": "jordan jordans jordanes air jordan aj10 aj 10 jordan10 tenis",
    "Jordan 11": "jordan jordans jordanes air jordan aj11 aj 11 jordan11 tenis",
    "Amiri": "amiri amirii amiry ammiri amiris ropa",
    "Balenciaga": "balenciaga balensiaga valenciaga balen balencia balensiaga ropa",
    "Bape": "bape bathing ape baep bapee a bathing ape ropa",
    "Burberry": "burberry burberi barberry burbery burverry ropa",
    "Supreme": "supreme suprem supremo supremme sup ropa",
    "Chrome Hearts": "chrome hearts chromehearts cromo cross ch sudadera ropa",
    "Chrome Hearts Cadenas": "chrome hearts cadenas chromehearts cadena cross ch joyeria plata collar accesorio",
    "Stock": "stock disponible inmediato entrega gorras cachuchas",
}

# Archivos a mover a _archivo/ (marcas descartadas + placeholders vacios)
ARCHIVE_GLOBS = [
    "Gucci*.html", "GucciOffTheGrid.html", "NewEra.html", "New-Era-*.html",
    "Dandy-*.html", "Barbas*.html", "Crocs.html",
]
ARCHIVE_EXACT = [
    "Alo.html", "Ami.html", "Boss.html", "Corteiz.html", "Diesel.html", "Dior.html",
    "DolceGabanna.html", "Fendi.html", "Gallery.html", "Hellstar.html",
    "PalmAngels.html", "sp5der.html", "AJ4Retro-Bred-Reimagined.html",
    "Amiri", "Ami",  # archivos raros sin extension
]

SIZE_RE = re.compile(
    r"talla|x?xs|x?xl|\bs a\b|\bm a\b|\d\s?pz|\bpz\b|\d/\d|^\s*\d|\ba \d|snap", re.I)

# ----------------------------------------------------------------------------
# Tallas y precios (para el carrito / sistema de tickets)
# ----------------------------------------------------------------------------
# Escalera de tallas de ropa, en orden. Se usa para expandir rangos "S a XXL".
SIZE_LADDER = ["XS", "S", "M", "L", "XL", "XXL", "3XL"]
SIZE_ALIASES = {"XXXL": "3XL", "2XL": "XXL"}
# Los tenis no traen talla en el catalogo: se usa la escalera MX estandar.
SNEAKER_SIZES = ["25", "25.5", "26", "26.5", "27", "27.5",
                 "28", "28.5", "29", "29.5", "30"]
UNITALLA = ["Unitalla"]


def parse_price(text):
    """'$2,850 MXN C/U' -> 2850. Devuelve 0 si no hay numero."""
    m = re.search(r"([\d][\d,]*)", text or "")
    return int(m.group(1).replace(",", "")) if m else 0


def _norm_size(tok):
    tok = tok.strip().upper().replace(".", "")
    return SIZE_ALIASES.get(tok, tok)


def parse_sizes(meta, category):
    """Convierte el texto de tallas del catalogo en una lista de opciones."""
    raw = (meta or "").strip()

    # Sin dato: tenis -> escalera MX; lo demas -> unitalla
    if not raw:
        return SNEAKER_SIZES[:] if "Jordan" in category else UNITALLA[:]

    low = raw.lower()

    # Caso mixto (conjunto hoodie + pantalon): no se puede partir en una lista
    if ":" in raw:
        return []

    # Unitalla / piezas sueltas / snapbacks
    if re.search(r"unitalla|\bpz\b|snap", low):
        return UNITALLA[:]

    # Tallas de gorra: "7", "7 1/8", "7 1/8 Y 7 1/4"
    if re.match(r"^\s*7(\s|$|/|\s*\d/\d)", raw):
        return [t.strip(" .") for t in re.split(r"\s+y\s+", raw, flags=re.I) if t.strip(" .")]

    # Lista numerica de pantalon: "30-32-34-36-38" o "30, 32, 34, 36, 38."
    nums = re.findall(r"\b(\d{2})\b", raw)
    if len(nums) >= 2 and not re.search(r"[a-z]", low.replace("talla", "")):
        return nums

    # Rango de ropa: "Talla S a XXL", "S a XL", "S-XL", "Talla xs a L"
    m = re.search(r"(x{0,3}s|m|l|x{0,2}l|3xl)\s*(?:a|-|hasta)\s*(x{0,3}s|m|l|x{0,2}l|3xl)",
                  low.replace("talla", ""), re.I)
    if m:
        a, b = _norm_size(m.group(1)), _norm_size(m.group(2))
        if a in SIZE_LADDER and b in SIZE_LADDER:
            i, j = SIZE_LADDER.index(a), SIZE_LADDER.index(b)
            if i <= j:
                return SIZE_LADDER[i:j + 1]

    return []


def product_id(detail_href, name):
    """Id estable por producto: el nombre del archivo de detalle, o el nombre."""
    base = detail_href or name
    return slugify(re.sub(r"\.html$", "", base))

# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------
def _find(pat, text, default=""):
    m = re.search(pat, text, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else default


def parse_category(path: Path):
    html = path.read_text(encoding="utf-8", errors="replace")
    chunks = html.split('class="product-item"')[1:]
    products = []
    for ch in chunks:
        href = _find(r'<a href="([^"]+\.html)"', ch)
        portada = _find(r'<img src="([^"]+)"', ch)
        name = _find(r'product-name"[^>]*>(.*?)</p>', ch)
        meta = _find(r'product-quality"[^>]*>(.*?)</p>', ch)
        price = _find(r'product-price"[^>]*>(.*?)</p>', ch)
        alt = _find(r'alt="([^"]*)"', ch)
        if not name:
            name = alt or "Sauce Store"
        name = name.rstrip(". ").strip() or alt
        is_size = bool(meta and SIZE_RE.search(meta))
        products.append({
            "name": name,
            "detail": href or "",
            "portada": portada,
            "price": price.replace("  ", " ").strip(),
            "sizes": meta if is_size else "",
            "quality": "" if is_size else meta,
            "gallery": [],
        })
    return products


def parse_gallery(path: Path):
    if not path.exists():
        return []
    html = path.read_text(encoding="utf-8", errors="replace")
    seen, out = set(), []
    for m in re.finditer(r'<a href="(img/[^"]+)"[^>]*data-lightbox', html, re.I):
        src = m.group(1)
        if src not in seen:
            seen.add(src)
            out.append(src)
    if not out:  # a veces sin lightbox, solo <img>
        for m in re.finditer(r'<img src="(img/[^"]+)"', html, re.I):
            src = m.group(1)
            if src not in seen:
                seen.add(src)
                out.append(src)
    return [s for s in out if (ROOT / s).exists()]  # descarta imagenes rotas


def snapshot():
    """Guarda una copia intacta de los HTML originales en _source/ (una sola vez)."""
    if SRC.exists():
        return
    SRC.mkdir()
    for slug, *_ in CATEGORIES:
        p = ROOT / slug
        if not p.exists():
            continue
        shutil.copy2(p, SRC / slug)
        for prod in parse_category(p):
            d = prod["detail"]
            if d and (ROOT / d).exists():
                (SRC / Path(d).parent).mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / d, SRC / d)
    print(f"  snapshot -> _source/ ({len(list(SRC.glob('*.html')))} archivos)")


def build_catalog():
    snapshot()
    cats = []
    seen_ids = {}
    for slug, title, group, folder in CATEGORIES:
        path = SRC / slug
        if not path.exists():
            print(f"  !! falta {slug}")
            continue
        products = parse_category(path)
        for p in products:
            if p["detail"]:
                p["gallery"] = parse_gallery(SRC / p["detail"])
            if not p["gallery"] and p["portada"]:
                p["gallery"] = [p["portada"]]
            p["category"] = title
            p["category_slug"] = slug
            # id unico: varios productos sin pagina de detalle comparten nombre
            # (p.ej. las 11 cadenas Chrome Hearts), asi que se numeran.
            base_id = product_id(p["detail"], p["name"])
            seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
            p["id"] = base_id if seen_ids[base_id] == 1 else f"{base_id}-{seen_ids[base_id]}"
            p["price_num"] = parse_price(p["price"])
            p["size_options"] = parse_sizes(p["sizes"], title)
        cats.append({"slug": slug, "title": title, "group": group,
                     "folder": folder, "products": products})
    return cats


# ----------------------------------------------------------------------------
# Plantillas
# ----------------------------------------------------------------------------
def head(title, desc=""):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc or 'Sauce Store — catalogo.'}">
<link rel="icon" href="img/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css">
<link rel="stylesheet" href="styles.css">
</head>
<body>"""


def nav(cats):
    groups = {}
    for c in cats:
        if c["group"] in ("tenis", "ropa", "accesorios"):
            groups.setdefault(c["group"], []).append(c)
    blocks = []
    for g in ("tenis", "ropa", "accesorios"):
        if g not in groups:
            continue
        links = "".join(
            f'<a href="{c["slug"]}">{c["title"]}</a>' for c in groups[g])
        blocks.append(f"""      <div class="nav-group">
        <button class="nav-trigger" aria-expanded="false">{MENU_LABELS[g]}</button>
        <div class="nav-panel"><div class="nav-panel-inner">{links}</div></div>
      </div>""")
    blocks.append('      <a class="nav-flat" href="Stock.html">Stock</a>')
    nav_html = "\n".join(blocks)

    mobile_sections = []
    for g in ("tenis", "ropa", "accesorios"):
        if g not in groups:
            continue
        links = "".join(
            f'<a href="{c["slug"]}">{c["title"]}</a>' for c in groups[g])
        mobile_sections.append(
            f'<div class="m-group"><span>{MENU_LABELS[g]}</span>{links}</div>')
    mobile_sections.append('<div class="m-group"><a href="Stock.html">Stock</a></div>')
    mobile_html = "\n".join(mobile_sections)

    return f"""<header class="site-header" id="siteHeader">
  <div class="header-inner">
    <a class="wordmark" href="index.html">SAUCE&nbsp;STORE<i>&#9733;</i></a>
    <nav class="nav-desktop">
{nav_html}
    </nav>
    <div class="header-actions">
      <button class="search-btn" id="searchBtn" aria-label="Buscar">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/></svg>
      </button>
      <a href="{IG}" target="_blank" rel="noopener">Instagram</a>
      <a href="{WA}" target="_blank" rel="noopener" class="ha-wa">WhatsApp</a>
      <a class="cart-btn" href="carrito.html" aria-label="Carrito">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 4h2l2.4 11.2a1 1 0 0 0 1 .8h8.5a1 1 0 0 0 1-.8L20 7H6"/><circle cx="10" cy="20" r="1.3"/><circle cx="17" cy="20" r="1.3"/></svg>
        <span class="cart-count" id="cartCount" hidden>0</span>
      </a>
      <button class="burger" id="burger" aria-label="Menu"><span></span><span></span><span></span></button>
    </div>
  </div>
</header>
<div class="mobile-menu" id="mobileMenu">
  <div class="mm-inner">
{mobile_html}
    <div class="m-social">
      <a href="{IG}" target="_blank" rel="noopener">Instagram</a>
      <a href="{WA}" target="_blank" rel="noopener">WhatsApp</a>
    </div>
  </div>
</div>
<div class="search-overlay" id="searchOverlay">
  <div class="search-box">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/></svg>
    <input type="text" id="searchInput" placeholder="Busca tu marca o modelo — Jordan, Balenciaga, Bape..." autocomplete="off" spellcheck="false">
    <button class="search-close" id="searchClose" aria-label="Cerrar">&times;</button>
  </div>
  <div class="search-hint" id="searchHint">Escribe una marca (aunque tenga una falta de ortografia) o el nombre de un modelo.</div>
  <div class="search-results" id="searchResults"></div>
</div>"""


def footer():
    return f"""<footer class="site-footer">
  <img class="foot-mascot" src="img/mascota-320.png" alt="Sauce Store" loading="lazy">
  <p class="foot-word">SAUCE&nbsp;STORE</p>
  <p class="foot-note">Catalogo visual. Para pedidos, contactanos.</p>
  <div class="foot-links">
    <a href="{IG}" target="_blank" rel="noopener">Instagram</a>
    <a href="{WA}" target="_blank" rel="noopener">WhatsApp</a>
  </div>
  <p class="foot-copy">&copy; Sauce Store</p>
</footer>
<a class="wa-float" href="{WA}" target="_blank" rel="noopener" aria-label="WhatsApp">
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor"><path d="M12.04 2c-5.46 0-9.9 4.44-9.9 9.9 0 1.75.46 3.45 1.32 4.95L2 22l5.3-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.9-4.44 9.9-9.9S17.5 2 12.04 2zm5.8 14.01c-.24.68-1.4 1.3-1.94 1.35-.5.05-1.13.24-3.66-.77-3.08-1.22-5.06-4.36-5.22-4.56-.15-.2-1.25-1.66-1.25-3.17 0-1.51.79-2.25 1.07-2.56.28-.31.61-.38.81-.38.2 0 .41 0 .58.01.19.01.44-.07.69.53.24.6.83 2.06.9 2.21.07.15.12.32.02.52-.1.2-.15.32-.3.5-.15.18-.31.4-.44.53-.15.15-.3.31-.13.6.17.29.76 1.25 1.63 2.03 1.12 1 2.06 1.31 2.35 1.46.29.15.46.12.63-.07.17-.2.73-.85.93-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.12.07.7-.17 1.38z"/></svg>
</a>
<script src="https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/fuse.js/6.6.2/fuse.min.js"></script>
<script src="app.js"></script>
<script src="search.js"></script>
<script src="cart.js"></script>
</body>
</html>"""


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def render_category(cat, cats):
    cards = []
    for i, p in enumerate(cat["products"]):
        meta = p["sizes"] or p["quality"] or ""
        tag = f'<span class="pc-meta">{meta}</span>' if meta else ""
        img = p["portada"] or (p["gallery"][0] if p["gallery"] else "")
        inner = f"""    <div class="pc-media"><img loading="lazy" src="{img}" alt="{p['name']}"></div>
    <div class="pc-info">
      <p class="pc-name">{p['name']}</p>
      {tag}
      <p class="pc-price">{p['price']}</p>
    </div>"""
        if p["detail"]:
            cards.append(f'<a class="product-card reveal" style="--d:{i%12*0.03:.2f}s" href="{p["detail"]}">\n{inner}\n</a>')
        else:
            # Sin pagina de detalle: el boton de carrito va en la tarjeta misma
            size = (p["size_options"] or ["Unitalla"])[0]
            btn = (f'<button class="pc-add" data-id="{p["id"]}" data-name="{p["name"]}"'
                   f' data-price="{p["price_num"]}" data-img="{img}" data-size="{size}">'
                   f'Agregar al carrito</button>')
            cards.append(f'<div class="product-card reveal no-link" style="--d:{i%12*0.03:.2f}s">\n{inner}\n{btn}\n</div>')
    grid = "\n".join(cards)
    n = len(cat["products"])
    return f"""{head(cat['title'] + " — Sauce Store", "Catalogo " + cat['title'] + " en Sauce Store.")}
{nav(cats)}
<main class="cat-page">
  <section class="cat-hero reveal">
    <p class="cat-kicker">Catalogo</p>
    <h1 class="cat-title">{cat['title']}</h1>
    <p class="cat-count">{n} {'modelo' if n==1 else 'modelos'}</p>
  </section>
  <section class="product-grid">
{grid}
  </section>
</main>
{footer()}"""


def render_detail(p, cat, cats):
    gallery = p["gallery"] or ([p["portada"]] if p["portada"] else [])
    main_img = gallery[0] if gallery else ""
    thumbs = "\n".join(
        f'      <button class="g-thumb{" is-active" if i==0 else ""}" data-src="{src}"><img loading="lazy" src="{src}" alt=""></button>'
        for i, src in enumerate(gallery))
    slides = "\n".join(
        f'    <a class="glink" href="{src}" data-gallery="prod"></a>' for src in gallery)
    meta_rows = ""
    if p["price"]:
        meta_rows += f'<div class="d-row"><span>Precio</span><b>{p["price"]}</b></div>'
    if p["sizes"]:
        meta_rows += f'<div class="d-row"><span>Tallas</span><b>{p["sizes"]}</b></div>'
    if p["quality"]:
        meta_rows += f'<div class="d-row"><span>Calidad</span><b>{p["quality"]}</b></div>'

    # otros modelos de la misma categoria
    others = [x for x in cat["products"] if x["detail"] and x["detail"] != p["detail"]][:6]
    rel = "\n".join(
        f'<a class="rel-card" href="{o["detail"]}"><img loading="lazy" src="{o["portada"] or (o["gallery"][0] if o["gallery"] else "")}" alt="{o["name"]}"><span>{o["name"]}</span></a>'
        for o in others)

    # Selector de talla + agregar al carrito
    opts = p.get("size_options") or []
    if opts:
        chips = "".join(
            f'<button type="button" class="size-chip" data-size="{s}">{s}</button>'
            for s in opts)
        size_block = f"""      <div class="d-sizes">
        <p class="d-sizes-label">Elige tu talla <b class="size-req">*</b></p>
        <div class="size-chips" id="sizeChips">{chips}</div>
      </div>"""
    else:
        # Producto sin lista de tallas (p.ej. conjuntos): talla libre
        hint = p["sizes"] or "Indica tu talla"
        size_block = f"""      <div class="d-sizes">
        <p class="d-sizes-label">Indica tu talla <b class="size-req">*</b></p>
        <input class="size-free" id="sizeFree" type="text" maxlength="40" placeholder="{hint}">
      </div>"""

    cart_block = f"""{size_block}
      <button class="d-cta" id="addToCart"
              data-id="{p['id']}" data-name="{p['name']}"
              data-price="{p['price_num']}" data-img="{main_img}">Agregar al carrito</button>
      <a class="d-cta d-cta-alt" href="{WA}" target="_blank" rel="noopener">Preguntar por este modelo</a>"""

    return f"""{head(p['name'] + " — Sauce Store", p['name'] + " — " + cat['title'] + " en Sauce Store.")}
{nav(cats)}
<main class="detail-page">
  <nav class="crumbs"><a href="index.html">Inicio</a> / <a href="{cat['slug']}">{cat['title']}</a> / <span>{p['name']}</span></nav>
  <div class="detail-grid">
    <section class="d-gallery">
      <div class="g-main"><img id="gMain" src="{main_img}" alt="{p['name']}"></div>
      <div class="g-thumbs">
{thumbs}
      </div>
      <div class="glinks" hidden>
{slides}
      </div>
      <button class="g-zoom" id="gZoom">Ver en grande</button>
    </section>
    <section class="d-info reveal">
      <p class="d-kicker">{cat['title']}</p>
      <h1 class="d-name">{p['name']}</h1>
      <div class="d-rows">{meta_rows}</div>
{cart_block}
      <div class="d-notes">
        <p>&#8226; Realiza tu pedido con el 50% y liquida al recibir (entrega en GDL, si eres de otro estado puedes hacer lo mismo pero pagas $200 de re envio).</p>
        <p>&#8226; Envios GRATIS directamente a tu casa: se liquida el total y llega por paqueteria a tu domicilio (TODO MÉXICO).</p>
        <p>&#8226; 10 a 15 dias despues del QC con fotos reales.</p>
      </div>
    </section>
  </div>
  <section class="related reveal">
    <h2>Tambien te puede interesar</h2>
    <div class="rel-strip">
{rel}
    </div>
  </section>
</main>
{footer()}"""


ESTADOS_MX = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Chiapas", "Chihuahua", "Ciudad de Mexico", "Coahuila", "Colima", "Durango",
    "Estado de Mexico", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco",
    "Michoacan", "Morelos", "Nayarit", "Nuevo Leon", "Oaxaca", "Puebla",
    "Queretaro", "Quintana Roo", "San Luis Potosi", "Sinaloa", "Sonora",
    "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatan", "Zacatecas",
]


def render_carrito(cats):
    return f"""{head("Carrito — Sauce Store", "Tu carrito en Sauce Store.")}
{nav(cats)}
<main class="cat-page">
  <section class="cat-hero">
    <p class="cat-kicker">Tu pedido</p>
    <h1 class="cat-title">Carrito</h1>
    <p class="cat-count" id="cartSummary">Cargando…</p>
  </section>

  <div class="cart-layout">
    <section class="cart-items" id="cartItems"></section>
    <aside class="cart-side" id="cartSide" hidden>
      <div class="d-rows">
        <div class="d-row"><span>Productos</span><b id="sumCount">0</b></div>
        <div class="d-row"><span>Subtotal</span><b id="sumTotal">$0 MXN</b></div>
      </div>
      <a class="d-cta" href="checkout.html">Finalizar pedido</a>
      <div class="d-notes">
        <p>&#8226; El siguiente paso es elegir apartado o liquidar, y llenar tus datos.</p>
        <p>&#8226; No se cobra nada en la pagina: se genera un ticket y te contactamos.</p>
      </div>
    </aside>
  </div>

  <div class="cart-empty" id="cartEmpty" hidden>
    <p>Tu carrito esta vacio.</p>
    <a class="hero-cta" href="index.html">Ver catalogo</a>
  </div>
</main>
{footer()}"""


def render_checkout(cats):
    estados = "".join(f'<option value="{e}">{e}</option>' for e in ESTADOS_MX)
    return f"""{head("Finalizar pedido — Sauce Store", "Genera tu ticket de pedido.")}
{nav(cats)}
<main class="cat-page">
  <section class="cat-hero">
    <p class="cat-kicker">Paso final</p>
    <h1 class="cat-title">Tu pedido</h1>
  </section>

  <form class="checkout" id="checkoutForm" novalidate>
    <div class="co-main">
      <section class="co-block">
        <h2 class="co-title"><span>01</span> Como quieres pagarlo</h2>
        <div class="co-options">
          <label class="co-opt">
            <input type="radio" name="modo" value="apartado" checked>
            <span class="co-opt-body">
              <b>Apartado del 50%</b>
              <i>Pagas la mitad ahora y liquidas al recibir.</i>
            </span>
          </label>
          <label class="co-opt">
            <input type="radio" name="modo" value="liquidar">
            <span class="co-opt-body">
              <b>Liquidar pedido</b>
              <i>Pagas el total y el envio va gratis a tu casa.</i>
            </span>
          </label>
        </div>
      </section>

      <section class="co-block">
        <h2 class="co-title"><span>02</span> Como lo recibes</h2>
        <div class="co-options">
          <label class="co-opt">
            <input type="radio" name="entrega" value="gdl" checked>
            <span class="co-opt-body">
              <b>Entrega en Guadalajara</b>
              <i>Nos ponemos de acuerdo por WhatsApp. Sin costo.</i>
            </span>
          </label>
          <label class="co-opt">
            <input type="radio" name="entrega" value="envio">
            <span class="co-opt-body">
              <b>Envio a domicilio</b>
              <i id="envioNota">Gratis si liquidas. Con apartado se suman $200 de reenvio.</i>
            </span>
          </label>
        </div>
      </section>

      <section class="co-block">
        <h2 class="co-title"><span>03</span> Tus datos</h2>
        <div class="co-grid">
          <label class="co-field">
            <span>Nombre completo *</span>
            <input type="text" name="nombre" maxlength="80" required>
          </label>
          <label class="co-field">
            <span>WhatsApp (10 digitos) *</span>
            <input type="tel" name="whatsapp" maxlength="20" inputmode="numeric"
                   placeholder="33 1234 5678" required>
          </label>
        </div>

        <div class="co-address" id="coAddress" hidden>
          <p class="co-sub">Direccion de envio</p>
          <div class="co-grid">
            <label class="co-field">
              <span>Estado *</span>
              <select name="estado"><option value="">Elige…</option>{estados}</select>
            </label>
            <label class="co-field">
              <span>Ciudad *</span>
              <input type="text" name="ciudad" maxlength="80">
            </label>
            <label class="co-field">
              <span>Calle *</span>
              <input type="text" name="calle" maxlength="120">
            </label>
            <label class="co-field">
              <span>Colonia *</span>
              <input type="text" name="colonia" maxlength="80">
            </label>
            <label class="co-field">
              <span>Numero ext. e int. *</span>
              <input type="text" name="numero" maxlength="40" placeholder="Ext. 123, Int. 4B">
            </label>
            <label class="co-field">
              <span>Entre calles *</span>
              <input type="text" name="entrecalles" maxlength="120">
            </label>
            <label class="co-field">
              <span>Codigo postal</span>
              <input type="text" name="cp" maxlength="8" inputmode="numeric">
            </label>
            <label class="co-field">
              <span>Referencias (opcional)</span>
              <input type="text" name="referencias" maxlength="120" placeholder="Casa blanca, porton negro…">
            </label>
          </div>
        </div>
      </section>

      <section class="co-block">
        <h2 class="co-title"><span>04</span> Metodo de pago</h2>
        <p class="co-hint">No se cobra nada aqui. Es solo para saber como vas a pagar.</p>
        <div class="co-options co-options-3">
          <label class="co-opt">
            <input type="radio" name="pago" value="transferencia" checked>
            <span class="co-opt-body"><b>Transferencia</b><i>Sin comision.</i></span>
          </label>
          <label class="co-opt">
            <input type="radio" name="pago" value="oxxo">
            <span class="co-opt-body"><b>Deposito OXXO</b><i>Sin comision.</i></span>
          </label>
          <label class="co-opt">
            <input type="radio" name="pago" value="tarjeta">
            <span class="co-opt-body"><b>Tarjeta</b><i>Se agrega 5% de comision.</i></span>
          </label>
        </div>
      </section>

      <!-- anti-spam: invisible para personas -->
      <div class="hp-field" aria-hidden="true">
        <label>No llenar<input type="text" name="apellido2" tabindex="-1" autocomplete="off"></label>
      </div>
    </div>

    <aside class="co-side">
      <p class="co-side-title">Resumen</p>
      <div class="co-lines" id="coLines"></div>
      <div class="d-rows" id="coTotals"></div>
      <button type="submit" class="d-cta" id="coSubmit">Generar mi ticket</button>
      <p class="co-error" id="coError" hidden></p>
      <div class="d-notes">
        <p>&#8226; Al generar el ticket nos llega tu pedido y te escribimos por WhatsApp.</p>
        <p>&#8226; Las tallas estan sujetas a disponibilidad; te confirmamos antes de cobrar.</p>
      </div>
    </aside>
  </form>
</main>
{footer()}"""


def render_ticket(cats):
    return f"""{head("Tu ticket — Sauce Store", "Ticket de tu pedido en Sauce Store.")}
{nav(cats)}
<main class="cat-page">
  <div class="ticket-wrap" id="ticketWrap" hidden>
    <section class="ticket">
      <div class="tk-head">
        <img class="tk-star" src="img/mascota-320.png" alt="Sauce Store">
        <p class="tk-brand">SAUCE&nbsp;STORE</p>
        <p class="tk-folio" id="tkFolio">—</p>
        <p class="tk-date" id="tkDate"></p>
      </div>
      <div class="tk-body">
        <div class="tk-lines" id="tkLines"></div>
        <div class="d-rows" id="tkTotals"></div>
        <div class="tk-client" id="tkClient"></div>
      </div>
      <div class="tk-foot">
        <p id="tkPayNote"></p>
        <p class="tk-small">Guarda una captura de este ticket. Te contactamos por WhatsApp
           para confirmar tallas y darte los datos de pago.</p>
      </div>
    </section>
    <div class="tk-actions">
      <a class="d-cta" href="{WA}" target="_blank" rel="noopener">Ir al WhatsApp</a>
      <button class="d-cta d-cta-alt" onclick="window.print()">Imprimir / Guardar PDF</button>
      <a class="tk-link" href="index.html">Volver al catalogo</a>
    </div>
  </div>

  <div class="cart-empty" id="ticketEmpty">
    <p>No hay ningun ticket para mostrar.</p>
    <a class="hero-cta" href="index.html">Ver catalogo</a>
  </div>
</main>
{footer()}"""


def render_referencias():
    folder = ROOT / "img" / "referencias-web"
    if not folder.exists():
        return ""
    files = sorted(folder.glob("refe-*.jpg"),
                    key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    if not files:
        return ""
    mid = (len(files) + 1) // 2
    rows = [files[:mid], files[mid:]]

    def row_html(items, rev):
        cards = "".join(
            f'<a class="ref-item" href="img/referencias-web/{f.name}" '
            f'data-gallery="referencias"><img loading="lazy" src="img/referencias-web/{f.name}" alt="Referencia Sauce Store"></a>'
            for f in items)
        cls = "marquee-rev" if rev else ""
        return f"""    <div class="marquee {cls}">
      <div class="marquee-track">{cards}{cards}</div>
    </div>"""

    tracks = "\n".join(row_html(r, i == 1) for i, r in enumerate(rows) if r)
    return f"""  <section class="referencias">
    <div class="sec-head reveal"><h2>Referencias</h2><span>{len(files)}</span></div>
    <p class="ref-note reveal">Capturas reales tomadas de nuestro Instagram en destacadas — pedidos ya entregados. (Anteriormente fuimos caps west, solo cambiamos el nombre)</p>
{tracks}
  </section>
"""


def render_index(cats):
    tiles = []
    real = [c for c in cats if c["group"] != "stock"]
    for i, c in enumerate(real):
        prods = c["products"]
        img = ""
        for p in prods:
            if p["portada"]:
                img = p["portada"]
                break
        tiles.append(f"""      <a class="cat-tile" href="{c['slug']}">
        <div class="ct-media"><img loading="lazy" src="{img}" alt="{c['title']}"></div>
        <div class="ct-label"><span>{c['title']}</span><i>&rarr;</i></div>
      </a>""")
    tiles_html = "\n".join(tiles)

    return f"""{head("Sauce Store — Catalogo", "Sauce Store: tenis y ropa. Catalogo visual con fotos reales.")}
{nav(cats)}
<main>
  <section class="hero" id="hero">
    <div class="hero-video">
      <video autoplay muted loop playsinline poster="img/video/intro.jpg">
        <source src="img/video/intro.webm" type="video/webm">
        <source src="img/video/intro.mp4" type="video/mp4">
      </video>
    </div>
    <div class="hero-copy">
      <p class="hero-tag">Tenis y ropa seleccionada &#8212; fotos reales, sin sorpresas.</p>
      <a href="#catalogo" class="hero-cta">Ver catalogo</a>
    </div>
    <div class="hero-scroll">Scroll</div>
  </section>

  <section class="statement reveal">
    <p>No somos otra tienda.<br>Cada modelo se elige por la mejor calidad, se fotografia real
       y se entrega como se ve. <b>Esto es Sauce&nbsp;Store.</b></p>
  </section>

  <section class="categories" id="catalogo">
    <div class="sec-head reveal"><h2>Categorias</h2><span>{len(real)}</span></div>
    <div class="cat-rail-wrap reveal">
      <button class="rail-arrow rail-prev" data-rail="prev" aria-label="Anterior">&#8592;</button>
      <div class="cat-rail" id="catRail">
        <div class="cat-track">
{tiles_html}
        </div>
      </div>
      <button class="rail-arrow rail-next" data-rail="next" aria-label="Siguiente">&#8594;</button>
    </div>
  </section>

  <section class="saludo reveal">
    <div class="saludo-video">
      <video autoplay muted loop playsinline poster="img/video/saludo.jpg">
        <source src="img/video/saludo.webm" type="video/webm">
        <source src="img/video/saludo.mp4" type="video/mp4">
      </video>
    </div>
    <div class="saludo-copy">
      <h2>Conocenos</h2>
      <p>Somos de Guadalajara, enviamos a TODO MÉXICO. Atendemos por WhatsApp e Instagram, contamos con más de 2 años trabajando y +200 referencias nos respaldan.</p>
      <a href="{WA}" target="_blank" rel="noopener" class="hero-cta">Escribenos</a>
    </div>
  </section>

{render_referencias()}
  <section class="avisos reveal">
    <div class="aviso">
      <h3>Proceso de compra</h3>
      <p>Elige tu modelo y crea tu ticket de compra en el carrito. 
      Nosotros te contactaremos para enviarte las formas de pago disponibles.
       </p>
    </div>
    <div class="aviso">
      <h3>Tiempo de entrega</h3>
      <p>Catalogo: 10 a 15 dias despues del QC. Stock: entrega al dia siguiente en persona o
     por Uber / paqueteria.</p>
    </div>
    <div class="aviso">
      <h3>Pagos</h3>
      <p>Transferencia, deposito OXXO o tarjeta (+5%). Entregas en GDL: efectivo,
         debito/credito y vales.</p>
    </div>
    <div class="aviso">
      <h3>Reembolsos</h3>
      <p>Producto distinto, dañado o problemas de aduana: se reenvia el par antes
         que un reembolso.
         </p>
    </div>
  </section>
</main>
{footer()}"""


# ----------------------------------------------------------------------------
# Archivado
# ----------------------------------------------------------------------------
def archive_old():
    dest = ROOT / "_archivo"
    dest.mkdir(exist_ok=True)
    moved = 0
    targets = set()
    for pat in ARCHIVE_GLOBS:
        targets.update(ROOT.glob(pat))
    for name in ARCHIVE_EXACT:
        p = ROOT / name
        if p.exists():
            targets.add(p)
    # placeholders vacios
    for p in ROOT.glob("*.html"):
        if p.stat().st_size == 0:
            targets.add(p)
    for p in targets:
        if p.is_file():
            shutil.move(str(p), str(dest / p.name))
            moved += 1
    d = ROOT / "Dandy"
    if d.is_dir():
        shutil.move(str(d), str(dest / "Dandy"))
    for lnk in (ROOT / "img").glob("*.lnk"):
        shutil.move(str(lnk), str(dest / lnk.name))
    print(f"  archivados {moved} archivos -> _archivo/")


# ----------------------------------------------------------------------------
def main():
    print("Parseando categorias...")
    snapshot()
    if "--archive" in sys.argv:
        archive_old()
    cats = build_catalog()

    (ROOT / "catalog.json").write_text(
        json.dumps(cats, ensure_ascii=False, indent=1), encoding="utf-8")

    total_p = total_g = 0
    written = 0
    for c in cats:
        (ROOT / c["slug"]).write_text(render_category(c, cats), encoding="utf-8")
        written += 1
        for p in c["products"]:
            total_p += 1
            total_g += len(p["gallery"])
            if p["detail"]:
                (ROOT / p["detail"]).write_text(
                    render_detail(p, c, cats), encoding="utf-8")
                written += 1
        no_gal = [p["name"] for p in c["products"]
                  if len(p["gallery"]) <= 1 and p["detail"]]
        flag = f"  ({len(no_gal)} sin galeria propia)" if no_gal else ""
        print(f"  {c['title']:22} {len(c['products']):3} productos{flag}")

    (ROOT / "index.html").write_text(render_index(cats), encoding="utf-8")
    written += 1

    # Paginas del sistema de tickets
    for fname, fn in (("carrito.html", render_carrito),
                      ("checkout.html", render_checkout),
                      ("ticket.html", render_ticket)):
        (ROOT / fname).write_text(fn(cats), encoding="utf-8")
        written += 1

    # productos.json: lo consume el carrito (frontend) y la validacion (backend).
    # El navegador NUNCA manda precios; se resuelven siempre contra este archivo.
    productos = {}
    for c in cats:
        for p in c["products"]:
            productos[p["id"]] = {
                "name": p["name"],
                "cat": c["title"],
                "price": p["price_num"],
                "sizes": p["size_options"],
                "img": p["portada"] or (p["gallery"][0] if p["gallery"] else ""),
                "url": p["detail"],
            }
    (ROOT / "productos.json").write_text(
        json.dumps(productos, ensure_ascii=False), encoding="utf-8")
    sin_talla = [k for k, v in productos.items() if not v["sizes"]]
    print(f"  productos.json -> {len(productos)} productos"
          f" ({len(sin_talla)} con talla libre)")

    # Indice para el buscador (nombre + alias de marca para tolerar errores de tipeo)
    search_docs = []
    for c in cats:
        alias = BRAND_ALIASES.get(c["title"], "")
        for p in c["products"]:
            if not p["detail"]:
                continue
            search_docs.append({
                "name": p["name"],
                "cat": c["title"],
                "url": p["detail"],
                "img": p["portada"] or (p["gallery"][0] if p["gallery"] else ""),
                "price": p["price"],
                "kw": alias,
            })
    (ROOT / "search.json").write_text(
        json.dumps(search_docs, ensure_ascii=False), encoding="utf-8")
    print(f"  search.json -> {len(search_docs)} productos indexados")

    print(f"\nOK: {written} HTML escritos | {total_p} productos | {total_g} imagenes")


if __name__ == "__main__":
    main()
