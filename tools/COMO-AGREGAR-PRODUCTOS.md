# Cómo agregar productos (la forma rápida)

## La regla de oro

**Lo que no cambia, no lo escribas.** Si toda la marca cuesta lo mismo y maneja
las mismas tallas, eso se pone **una sola vez** en el comando, no en cada foto.

---

## Forma rápida: una carpeta por modelo

Dentro de `img/` creas la carpeta de la marca, y adentro **una carpeta por modelo**
con **solo el nombre**:

```
img/Nueva Marca/
    Super Star Blancos/      <- solo el nombre, nada más
        foto1.png
        foto2.png
        foto3.png
    Super Star Gold/
        foto1.png
        ...
```

Y corres **un solo comando**:

```bash
python tools/importar.py --desde "img/Nueva Marca" --marca "Nombre Marca" --precio 2300 --tallas "EU 35-45"
python tools/build.py
```

Eso es todo. Las fotos pueden llamarse como sea: se ordenan solas por número
(`foto1`, `foto2`, `foto10` quedan en ese orden) y **la primera es la portada**.

### Truco de Windows que ahorra muchísimo

Para numerar fotos: selecciónalas todas → **F2** → escribe `foto` → **Enter**.
Windows las nombra `foto (1)`, `foto (2)`, `foto (3)`… en un solo paso.

---

## Si un modelo tiene precio o tallas distintas

Se lo pones a esa carpeta y manda sobre el general:

```
Super Star Blancos/                     <- usa el precio del comando
LV Trainer Azul - 3000/                 <- este cuesta distinto
LV Skate Negros - 3100 - EU 39-46/      <- precio y tallas propias
```

---

## Comparación real (Golden Goose, 11 modelos)

| | Antes | Ahora |
|---|---|---|
| Renombrar archivos | 51 archivos, cada uno con nombre + número + precio + tallas | 11 carpetas, solo el nombre |
| Escribir "$2300" | 51 veces | 1 vez |
| Escribir las tallas | 51 veces | 1 vez |

---

## Las tallas

- **Tenis con tallas europeas:** `--tallas "EU 35-45"` → se convierten solas a
  mexicanas. El cliente ve `27.5` y a ti te llega `27.5 MX (43 EU)` para pedirle
  al proveedor.
- **Ropa:** `--tallas "S a XXL"`
- **Si no pones nada:** tenis toma MX 25-30, ropa S-XXL, accesorios Unitalla.

---

## Marca nueva

Si la marca no existe todavía, avísame: hay que darla de alta en dos listas
(`CATEGORIES` en `build.py` y `CARPETAS` en `importar.py`). Son 2 líneas.

---

## Al terminar

```bash
git add -A
git commit -m "productos nuevos"
git push
```

Y mueve los originales a `Escritorio/FOTOS-ORIGINALES-SAUCE/<Marca>/` para que
el proyecto no engorde.
