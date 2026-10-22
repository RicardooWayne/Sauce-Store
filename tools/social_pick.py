# -*- coding: utf-8 -*-
"""
Que producto publica el bot y cuando.

- deal_of_day(): el "producto del dia", calculado EXACTAMENTE igual que la web
  (app.js / pedido.js): categoria del dia con la misma mezcla de bits y luego un
  modelo dentro de ella. Asi la historia de las 12:00 am siempre coincide con el
  sitio.
- picks_del_dia(): las publicaciones de 10 am / 4 pm / 8 pm. No guarda estado: todo se
  calcula a partir de la fecha. Ningun producto se repite hasta dar la vuelta al catalogo
  completo, y en un mismo dia no salen dos de la misma categoria.
"""
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _hash(s):
    h = 5381
    b = s.encode("utf-16-le")                    # igual que charCodeAt de JavaScript
    for i in range(0, len(b), 2):
        h = (h * 33 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    return h


def _mix(x):
    x &= 0xFFFFFFFF
    x = ((x ^ (x >> 16)) * 2246822507) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 3266489909) & 0xFFFFFFFF
    x ^= x >> 16
    return x & 0xFFFFFFFF


def deal_of_day(prods, day):
    """prods: dict de productos.json (con su orden original). day: 'AAAA-MM-DD' hora de Mexico."""
    ids = list(prods.keys())
    if not ids:
        return None
    seen, cats = set(), []
    for i in ids:
        c = prods[i].get("cat")
        if c and c not in seen:
            seen.add(c)
            cats.append(c)
    cat = cats[_mix(_hash(day)) % len(cats)] if cats else None
    pool = [i for i in ids if prods[i].get("cat") == cat] if cat else ids
    if not pool:
        pool = ids
    return pool[_mix(_hash(day + "|" + str(cat))) % len(pool)]


def deals_cercanos(prods, day, rango=45):
    """Productos del dia de +-rango dias alrededor de `day`: la bolsa aleatoria no
    los saca, asi un producto no aparece como oferta un dia y de relleno otro."""
    d0 = date.fromisoformat(day)
    return {deal_of_day(prods, (d0 + timedelta(days=k)).isoformat()) for k in range(-rango, rango + 1)}


EPOCH = date(2026, 1, 1)


def _orden(ids, seed):
    """Orden mezclado FIJO de todos los productos. Se ordena por un hash de (semilla+id):
    asi, cuando se agrega un producto nuevo solo se mete en un lugar al azar y los demas
    conservan su orden relativo (no se "revuelve" todo)."""
    return sorted(ids, key=lambda i: (_mix(_hash(seed + "|" + i)), i))


def picks_del_dia(prods, day, n=3, seed="sauce-store"):
    """Los n productos aleatorios del dia (10 am, 4 pm, 8 pm), SIN guardar estado.

    Se recorre el orden mezclado de a 3 por dia, asi que ningun producto vuelve a salir
    hasta dar la vuelta completa (con ~800 productos, unos 8 meses). Si el producto que toca
    no sirve (es un producto del dia cercano, o su categoria ya salio hoy), se toma otro de
    la mitad opuesta del orden: tardara meses en volver a tocarle por turno.
    """
    ids = list(prods.keys())
    orden = _orden(ids, seed)
    N = len(orden)
    d = (date.fromisoformat(day) - EPOCH).days
    vetados = deals_cercanos(prods, day)
    deal = deal_of_day(prods, day)
    usadas = {prods[deal].get("cat")} if deal else set()
    res = []
    for slot in range(n):
        base = (d * n + slot) % N
        posiciones = [base] + [(base + N // 2 + k) % N for k in range(N)]
        for pos in posiciones:
            pid = orden[pos]
            if pid in vetados or pid in res:
                continue
            if prods[pid].get("cat") in usadas:
                continue
            res.append(pid)
            usadas.add(prods[pid].get("cat"))
            break
    return res
