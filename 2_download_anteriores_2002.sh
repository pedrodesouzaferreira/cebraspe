#!/bin/bash
# Download the pre-2002 CESPE archive (concursos/_antigos/anteriores_2002/<year>/<concurso>/Arquivos/*).
#
# The live year/cover index pages return HTTP 500, so we ENUMERATE the file list
# from the Wayback Machine (CDX API) and DOWNLOAD from the live cespe.unb.br site
# (which still serves the individual files). Anything missing on live falls back to
# the Wayback snapshot. Files are mostly .zip (old editais/results) -> unzip later.
#
# Paths relative to this script (assumes <CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
LIST="$RAW/cespe_urls/urls_anteriores_2002_files.txt"
for c in curl wget; do command -v $c >/dev/null || { echo "ERROR: $c not found"; exit 1; }; done
mkdir -p "$(dirname "$LIST")"

echo "[1/3] Enumerating file list from Wayback CDX ..."
CDX="https://web.archive.org/cdx/search/cdx?url=cespe.unb.br/concursos/_antigos/anteriores_2002&matchType=prefix&collapse=urlkey&fl=original&output=text"
curl -sG "$CDX" \
  | sed -E 's/:80\//\//' \
  | sed -E 's#/concursoS/#/concursos/#g' \
  | grep -iE '/[^/]+\.[a-z0-9]{2,4}$' \
  | grep -viE '\.asp($|\?)|/default\.' \
  | sort -u > "$LIST"
echo "     $(grep -c . "$LIST") files listed -> ${LIST#$RAW/}"

echo "[2/3] Downloading from live cespe.unb.br (mirroring tree) ..."
# -x keeps host+path dirs -> $RAW/www.cespe.unb.br/concursos/_antigos/anteriores_2002/...
wget -x --timestamping --tries=3 --wait=0.5 --random-wait --limit-rate=500k \
     -e robots=off -P "$RAW" -i "$LIST" 2>/dev/null

echo "[3/3] Wayback fallback for anything missing/empty on live ..."
recovered=0; dead=0; ok=0
while IFS= read -r url; do
  [ -z "$url" ] && continue
  rel="${url#http://}"; rel="${rel#https://}"          # www.cespe.unb.br/concursos/.../c1.zip
  dst="$RAW/$rel"
  if [ -s "$dst" ]; then ok=$((ok+1)); continue; fi
  mkdir -p "$(dirname "$dst")"
  if wget -q -O "$dst" "https://web.archive.org/web/2id_/$url" && [ -s "$dst" ]; then
    recovered=$((recovered+1))
  else
    rm -f "$dst" 2>/dev/null; dead=$((dead+1)); echo "  DEAD (live+wayback): $rel"
  fi
done < "$LIST"
echo
echo "Live OK: $ok | Recovered via Wayback: $recovered | Dead: $dead | Total: $(grep -c . "$LIST")"
echo "Note: files are mostly .zip -> unzip before pdftotext. Tree: $RAW/www.cespe.unb.br/concursos/_antigos/anteriores_2002/"
