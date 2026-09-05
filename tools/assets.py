#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Procesa la mascota (jpg -> png transparente) y los videos (ffmpeg -> web).

IMPORTANTE: los videos NO se recolorean ni se les hace chroma-key. El fondo crema
original se conserva tal cual porque en la web viven sobre un panel del mismo
crema. Asi la identidad (colores de la estrella, tenis, letras) queda intacta.
"""
import subprocess
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = Path.home() / "OneDrive" / "Escritorio"
FFMPEG = Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe"
FF = str(FFMPEG) if FFMPEG.exists() else "ffmpeg"

MASCOT_SRC = DESKTOP / "MASCOTA SAUCE STORE.jpg"
INTRO_SRC = DESKTOP / "MASCOTA SAUCE ANIMACION PIES.mp4"
SALUDO_SRC = DESKTOP / "MASCOTA SAUCE STORE SALUDO.mov"
VID_OUT = ROOT / "img" / "video"


def remove_bg(src, dst, tol=48):
    im = src if isinstance(src, Image.Image) else Image.open(src)
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    cs = [px[1, 1], px[w - 2, 1], px[1, h - 2], px[w - 2, h - 2]]
    br = sum(c[0] for c in cs) // 4
    bg = sum(c[1] for c in cs) // 4
    bb = sum(c[2] for c in cs) // 4
    t2 = tol * tol

    def near(c):
        dr, dg, db = c[0] - br, c[1] - bg, c[2] - bb
        return dr * dr + dg * dg + db * db <= t2

    mask = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if mask[i] or not near(px[x, y]):
            continue
        mask[i] = 1
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))

    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    for y in range(h):
        r = y * w
        for x in range(w):
            if mask[r + x]:
                ap[x, y] = 0
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.1))
    im.putalpha(alpha)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    im.save(dst)
    print(f"  {Path(dst).name}  {im.size}")
    return im


def do_mascot():
    if not MASCOT_SRC.exists():
        print("  !! falta", MASCOT_SRC.name)
        return
    full = remove_bg(MASCOT_SRC, ROOT / "img" / "mascota.png")
    for size in (768, 320):
        c = full.copy()
        c.thumbnail((size, size), Image.LANCZOS)
        c.save(ROOT / "img" / f"mascota-{size}.png")
        print(f"  mascota-{size}.png  {c.size}")


def run(cmd):
    print("  $ ffmpeg", cmd[-1].split("/")[-1])
    subprocess.run(cmd, check=True, capture_output=True)


def report_bg(src):
    tmp = VID_OUT / "_p.png"
    VID_OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([FF, "-y", "-ss", "1", "-i", str(src), "-frames:v", "1", str(tmp)],
                   check=True, capture_output=True)
    im = Image.open(tmp).convert("RGB")
    c = im.getpixel((3, 3))
    tmp.unlink()
    hexc = "#%02X%02X%02X" % c
    print(f"  {src.name}: fondo {hexc}")
    return hexc


def do_video(src, name, max_alto=720):
    """Comprime el video para web sin perder calidad visible.

    Son animaciones 2D de colores planos, que comprimen muchisimo mejor que
    video real. Las claves:
      - NUNCA agrandar: si el original ya es de 720p, se deja en 720p.
        (Antes se escalaba a 800 de alto, o sea se agrandaba, y por eso pesaba
        el triple sin verse mejor.)
      - '-tune animation' en h264: ajusta el codificador justo para dibujos.
      - CRF mas alto del que usarias en video real; en dibujo plano no se nota.
    """
    if not src.exists():
        print("  !! falta", src.name)
        return
    VID_OUT.mkdir(parents=True, exist_ok=True)
    mp4 = VID_OUT / f"{name}.mp4"
    webm = VID_OUT / f"{name}.webm"
    jpg = VID_OUT / f"{name}.jpg"

    # Reduce solo si el original es mas alto que max_alto; nunca agranda.
    vf = f"scale=-2:'min({max_alto},ih)':flags=lanczos"

    run([FF, "-y", "-i", str(src), "-an", "-vf", vf, "-c:v", "libx264",
         "-tune", "animation", "-profile:v", "high", "-crf", "24",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)])
    run([FF, "-y", "-i", str(src), "-an", "-vf", vf, "-c:v", "libvpx-vp9",
         "-b:v", "0", "-crf", "34", "-row-mt", "1", "-deadline", "good",
         "-cpu-used", "2", "-pix_fmt", "yuv420p", str(webm)])
    run([FF, "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", "-q:v", "3", str(jpg)])
    for f in (webm, mp4, jpg):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")


REF_SRC = ROOT / "img" / "REFERENCIAS"
REF_OUT = ROOT / "img" / "referencias-web"


def do_referencias():
    if not REF_SRC.exists():
        print("  !! falta img/REFERENCIAS/")
        return
    REF_OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(
        REF_SRC.glob("*.*"),
        key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0))
    for i, f in enumerate(files, 1):
        im = Image.open(f).convert("RGB")
        im.thumbnail((760, 1400), Image.LANCZOS)
        out = REF_OUT / f"refe-{i}.jpg"
        im.save(out, "JPEG", quality=82, optimize=True)
    total = sum(p.stat().st_size for p in REF_OUT.glob("*.jpg")) // 1024
    print(f"  {len(files)} referencias -> img/referencias-web/  ({total} KB)")


def do_og_image():
    """Imagen 1200x630 para la vista previa al compartir el link.

    Es lo que se ve cuando pegas la direccion en WhatsApp, Instagram o Facebook.
    Sin esto solo aparece la URL pelona.
    """
    # Los originales viven fuera del proyecto; se usa la version .webp
    mascota = next((ROOT / "img" / n for n in
                    ("mascota.webp", "mascota-768.webp", "mascota.png", "mascota-768.png")
                    if (ROOT / "img" / n).exists()), None)
    if not mascota:
        print("  !! falta la mascota, se omite la portada social")
        return

    W, H = 1200, 630
    card = Image.new("RGB", (W, H), (244, 237, 221))   # crema de la marca
    m = Image.open(mascota).convert("RGBA")
    m.thumbnail((int(H * 0.78), int(H * 0.78)), Image.LANCZOS)
    card.paste(m, ((W - m.width) // 2, (H - m.height) // 2 - 24), m)

    out = ROOT / "img" / "og-sauce-store.jpg"
    card.save(out, "JPEG", quality=88, optimize=True)
    print(f"  og-sauce-store.jpg  {out.stat().st_size // 1024} KB  ({W}x{H})")


def main():
    args = sys.argv[1:]
    if "og" in args:
        print("Portada social:")
        do_og_image()
        return
    if not args or "mascot" in args:
        print("Mascota:")
        do_mascot()
    if not args or "referencias" in args:
        print("Referencias:")
        do_referencias()
    if not args or "video" in args:
        print("Fondo de los videos:")
        report_bg(INTRO_SRC)
        report_bg(SALUDO_SRC)
        print("Video intro:")
        do_video(INTRO_SRC, "intro")
        print("Video saludo:")
        do_video(SALUDO_SRC, "saludo")


if __name__ == "__main__":
    main()
