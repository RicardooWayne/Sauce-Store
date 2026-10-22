# -*- coding: utf-8 -*-
"""
Ayudante de configuracion de Meta (solo LEE, no publica nada).

Lo corres TU en tu computadora; los datos que escribas no pasan por ningun lado salvo
directo a Meta. Nunca pegues estos tokens en un chat ni los subas al repo: van solo
en GitHub > Settings > Secrets.

Paso A (una sola vez): convierte el token corto de Graph API Explorer en el token de
PAGINA que no caduca, y te muestra el ID de tu pagina y el de tu Instagram:

    python tools/social_setup.py --intercambiar

Paso B (cuando ya tengas el token de pagina): revisa que sirva para Facebook e Instagram:

    python tools/social_setup.py --revisar
"""
import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com"


def get(ruta, params):
    url = "%s/%s?%s" % (GRAPH, ruta, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(cuerpo).get("error", {}).get("message", cuerpo)
        except Exception:
            msg = cuerpo
        sys.exit("Meta respondio con error: %s" % msg)


def pedir(nombre, env, secreto=True):
    v = os.environ.get(env, "").strip()
    if v:
        return v
    return (getpass.getpass if secreto else input)("%s: " % nombre).strip()


def intercambiar():
    app_id = pedir("ID de la app", "META_APP_ID", secreto=False)
    app_secret = pedir("Clave secreta de la app (no se ve al escribir)", "META_APP_SECRET")
    corto = pedir("Token de usuario de Graph API Explorer (no se ve al escribir)", "META_USER_TOKEN")
    largo = get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id,
                                       "client_secret": app_secret, "fb_exchange_token": corto})
    tok = largo.get("access_token")
    if not tok:
        sys.exit("No se obtuvo el token largo: %s" % largo)
    pags = get("me/accounts", {"access_token": tok,
                               "fields": "id,name,access_token,instagram_business_account{id,username}"})
    data = pags.get("data", [])
    if not data:
        sys.exit("Esa cuenta no administra ninguna pagina (o faltaron permisos al generar el token).")
    print("\nPaginas que administras:\n")
    for i, p in enumerate(data, 1):
        ig = p.get("instagram_business_account") or {}
        print("[%d] %s" % (i, p.get("name")))
        print("    FB_PAGE_ID  = %s" % p.get("id"))
        print("    IG_USER_ID  = %s   (%s)" % (ig.get("id", "SIN INSTAGRAM VINCULADO"),
                                                ("@" + ig["username"]) if ig.get("username") else "-"))
        print("    META_PAGE_TOKEN = %s" % p.get("access_token"))
        print()
    print("Copia FB_PAGE_ID, IG_USER_ID y META_PAGE_TOKEN de TU pagina a GitHub > Settings > Secrets.")
    print("Este token de pagina no caduca mientras no cambies tu contrasena ni quites la app.")


def revisar():
    tok = pedir("META_PAGE_TOKEN (no se ve al escribir)", "META_PAGE_TOKEN")
    page = get("me", {"access_token": tok, "fields": "id,name"})
    print("Pagina:", page.get("name"), "| FB_PAGE_ID =", page.get("id"))
    ig = get(page["id"], {"access_token": tok, "fields": "instagram_business_account{id,username}"})
    cuenta = ig.get("instagram_business_account")
    if not cuenta:
        sys.exit("Esa pagina NO tiene un Instagram profesional vinculado.")
    print("Instagram: @%s | IG_USER_ID = %s" % (cuenta.get("username"), cuenta.get("id")))
    prueba = get(cuenta["id"], {"access_token": tok, "fields": "username,media_count"})
    print("El token puede leer tu Instagram (publicaciones: %s). Todo listo." % prueba.get("media_count"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intercambiar", action="store_true")
    ap.add_argument("--revisar", action="store_true")
    a = ap.parse_args()
    if a.intercambiar:
        intercambiar()
    elif a.revisar:
        revisar()
    else:
        ap.print_help()
