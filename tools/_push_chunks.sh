#!/usr/bin/env bash
# Sube el lote grande en pedazos de ~60-90 MB para no reventar el push de GitHub.
set -u
cd "$(dirname "$0")/.."

commit_push() {   # $1 = mensaje
  git commit -q -m "$1" || { echo "  (nada que commitear)"; return 0; }
  echo ">> push: $1"
  for intento in 1 2 3; do
    if git push origin main 2>&1 | tail -2; then echo "  OK"; return 0; fi
    echo "  reintento $intento..."
    sleep 5
  done
  echo "  !! FALLO tras 3 intentos"
  return 1
}

# Carpetas grandes: se parten en 2 commits (mitad y mitad)
push_folder_split() {   # $1 = carpeta   $2 = nombre
  mapfile -t files < <(git ls-files --others --exclude-standard "$1" ; git diff --name-only "$1")
  local n=${#files[@]}
  if [ "$n" -eq 0 ]; then return 0; fi
  local mid=$(( (n + 1) / 2 ))
  git add "${files[@]:0:mid}"
  commit_push "Fotos $2 (1/2)"
  git add "${files[@]:mid}"
  commit_push "Fotos $2 (2/2)"
}

echo "===== 1. Herramientas y config ====="
git add .gitignore tools/ styles.css app.js cart.js 2>/dev/null
commit_push "Importador del proveedor: modo album, medias tallas, envio variable, limpieza de codigos"

echo "===== 2. Carpetas grandes (partidas) ====="
push_folder_split img/Balenciaga-3XL   "Balenciaga 3XL"
push_folder_split img/Uggs             "Uggs"
push_folder_split img/Balenciaga-Runner "Balenciaga Runner"

echo "===== 3. Carpetas medianas ====="
for pair in \
  "img/Balenciaga-Defender:Balenciaga Defender" \
  "img/Balenciaga-6XL:Balenciaga 6XL" \
  "img/Balenciaga-10XL:Balenciaga 10XL" \
  "img/Balenciaga-Basketball:Balenciaga Basketball" \
  "img/Nocta:Nocta" \
  "img/Nike-Dunk:Nike Dunk" \
  "img/Bapesta:Bapesta" \
  "img/Timberland:Timberland" \
  "img/Off-White:Off White" \
  "img/Dior:Dior" \
  "img/Alexander-McQueen:Alexander McQueen" \
  "img/Amiri-Tenis:Amiri" \
  "img/Louis-Vuitton:Louis Vuitton nuevos" ; do
  d="${pair%%:*}"; n="${pair##*:}"
  git add "$d" 2>/dev/null
  commit_push "Fotos $n"
done

echo "===== 4. Resto (HTML, json, lo que quede) ====="
git add -A
commit_push "Lote grande del proveedor: +482 productos de tenis (paginas y catalogo)"

echo
echo "===== ESTADO FINAL ====="
git log --oneline origin/main..main | wc -l
echo "commits pendientes de subir (0 = todo arriba)"
echo "PUSH CHUNKS TERMINADO"
