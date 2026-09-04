#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Procesa la mascota (jpg -> png transparente) y los videos (ffmpeg -> web)."""
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


def remove_bg(src: Path, dst: Path, tol=48):
    im = src if isinstance(src, Image.Image) else Image.open(src)
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    # color de fondo = promedio de esquinas
    cs = [px[1, 1], px[w - 2, 1], px[1, h - 2], px[w - 2, h - 2]]
    br = sum(c[0] for c in cs) // 4
    bg = sum(c[1] for c in cs) // 4
    bb = sum(c[2] for c in cs) // 4
    t2 = tol * tol

    def near(c):
        dr, dg, db = c[0] - br, c[1] - bg, c[2] - bb
        return dr * dr + dg * dg + db * db <= t2

    # flood fill desde el borde -> solo toca fondo conectado
    mask = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            q.append((x, y))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if mask[i] or not near(px[x, y]):
            continue
        mask[i] = 1
        if x > 0:
            q.append((x - 1, y))
        if x < w - 1:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y < h - 1:
            q.append((x, y + 1))

    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    for y in range(h):
        row = y * w
        for x in range(w):
            if mask[row + x]:
                ap[x, y] = 0
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(alpha)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    im.save(dst)
    print(f"  {dst.name}  {im.size}")
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
    print("  $", " ".join(Path(c).name if "/" in c or "\\" in c else c for c in cmd)[:160])
    subprocess.run(cmd, check=True, capture_output=True)


def do_video(src: Path, name: str, w: int, h: int, key="0xF7E2C6",
             sim="0.18", blend="0.014", bg="0x0E0E0E"):
    """Recorta el fondo crema del video y lo funde con el fondo del sitio.

    webm  -> VP9 con canal alpha real (fondo transparente).
    mp4   -> keyeado y compuesto sobre el negro del sitio (fallback Safari/iOS).
    jpg   -> poster compuesto sobre el negro.
    """
    if not src.exists():
        print("  !! falta", src.name)
        return
    VID_OUT.mkdir(parents=True, exist_ok=True)
    mp4 = VID_OUT / f"{name}.mp4"
    webm = VID_OUT / f"{name}.webm"
    jpg = VID_OUT / f"{name}.jpg"
    scale = f"scale={w}:{h}:flags=lanczos"
    key_fx = f"{scale},colorkey={key}:{sim}:{blend}"

    run([FF, "-y", "-i", str(src), "-an", "-vf",
         f"{key_fx},format=yuva420p", "-c:v", "libvpx-vp9", "-b:v", "0",
         "-crf", "32", "-row-mt", "1", "-pix_fmt", "yuva420p", str(webm)])

    fc = (f"[1:v]{key_fx}[fg];[0:v][fg]overlay=shortest=1,format=yuv420p[v]")
    run([FF, "-y", "-f", "lavfi", "-i", f"color=c={bg}:s={w}x{h}:r=30",
         "-i", str(src), "-filter_complex", fc, "-map", "[v]", "-an",
         "-c:v", "libx264", "-profile:v", "high", "-crf", "24",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)])

    run([FF, "-y", "-f", "lavfi", "-i", f"color=c={bg}:s={w}x{h}",
         "-i", str(src), "-filter_complex",
         f"[1:v]{key_fx}[fg];[0:v][fg]overlay[v]", "-map", "[v]",
         "-frames:v", "1", "-q:v", "3", str(jpg)])

    for f in (webm, mp4, jpg):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")


def probe_corner(src: Path):
    """Saca un frame y reporta el color de la esquina (para fundir el fondo)."""
    tmp = VID_OUT / "_probe.png"
    VID_OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([FF, "-y", "-i", str(src), "-frames:v", "1", str(tmp)],
                   check=True, capture_output=True)
    im = Image.open(tmp).convert("RGB")
    w, h = im.size
    cs = [im.getpixel(p) for p in [(3, 3), (w - 4, 3), (3, h - 4), (w - 4, h - 4)]]
    tmp.unlink(missing_ok=True)
    avg = tuple(sum(c[i] for c in cs) // 4 for i in range(3))
    print(f"  {src.name}: esquinas {cs} -> promedio #{avg[0]:02x}{avg[1]:02x}{avg[2]:02x}")
    return avg


def main():
    if "mascot" in sys.argv or len(sys.argv) == 1:
        print("Mascota:")
        do_mascot()
    if "video" in sys.argv or len(sys.argv) == 1:
        print("Video saludo - color de fondo:")
        probe_corner(SALUDO_SRC)
        print("Video intro:")
        do_video(INTRO_SRC, "intro", 1280, 720)
        print("Video saludo:")
        do_video(SALUDO_SRC, "saludo", 970, 720)


if __name__ == "__main__":
    main()
