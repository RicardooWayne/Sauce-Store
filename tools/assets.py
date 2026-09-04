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


def do_video(src, name, height=800):
    if not src.exists():
        print("  !! falta", src.name)
        return
    VID_OUT.mkdir(parents=True, exist_ok=True)
    mp4 = VID_OUT / f"{name}.mp4"
    webm = VID_OUT / f"{name}.webm"
    jpg = VID_OUT / f"{name}.jpg"
    vf = f"scale=-2:{height}:flags=lanczos"
    run([FF, "-y", "-i", str(src), "-an", "-vf", vf, "-c:v", "libx264",
         "-profile:v", "high", "-crf", "17", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(mp4)])
    run([FF, "-y", "-i", str(src), "-an", "-vf", vf, "-c:v", "libvpx-vp9",
         "-b:v", "0", "-crf", "20", "-row-mt", "1", "-pix_fmt", "yuv420p", str(webm)])
    run([FF, "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", "-q:v", "2", str(jpg)])
    for f in (webm, mp4, jpg):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")


def main():
    args = sys.argv[1:]
    if not args or "mascot" in args:
        print("Mascota:")
        do_mascot()
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
