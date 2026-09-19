#!/bin/bash
# Idempotent importer for the CESPE legacy site (cespe.unb.br) — ALL eras.
#
#   PART 1: 2002-2019 concursos, from cespe_urls/urls_YYYY.txt (cover-page recursive wget).
#           Skips concursos that already have docs (metadata check -> NO Dropbox hydration).
#   PART 2: pre-2002 archive (_antigos/anteriores_2002/...). The live index pages return 500,
#           so we enumerate the file list from the Wayback Machine (CDX) and download from the
#           live site, falling back to the Wayback snapshot per file. Files are mostly .zip
#           (unzip later with 01_unzip_old.sh).
#
# Everything mirrors into Raw Data/www.cespe.unb.br/...  Re-run anytime (idempotent).
#   FULL=1      -> Part 1 also re-runs wget on already-present concursos (top-up partials)
#   SKIP_PRE=1  -> skip Part 2 (pre-2002)
#   REFRESH=1   -> Part 2 re-queries the Wayback CDX list instead of reusing the cached one
# Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
FULL="${FULL:-0}"; SKIP_PRE="${SKIP_PRE:-0}"; REFRESH="${REFRESH:-0}"
command -v wget >/dev/null || { echo "ERROR: wget not found"; exit 1; }
cd "$RAW" || { echo "cannot cd $RAW"; exit 1; }

has_docs() {  # $1 = concurso dir; true if it holds a real file (not just index.html)
  [ -d "$1" ] || return 1
  [ -n "$(find "$1" -type f ! -iname 'index.html' ! -name '.DS_Store' -print -quit 2>/dev/null)" ]
}
fetch_one() {  # $1 = cover-page URL
  wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber \
       --wait=1 --random-wait --limit-rate=500k "$1" >/dev/null 2>&1
}

echo "=== PART 1: 2002-2019 (cover pages) ==="
down=0; skip=0; empty=0; empties=""
for lst in cespe_urls/urls_*.txt; do
  base="$(basename "$lst")"
  case "$base" in urls_[0-9][0-9][0-9][0-9].txt) : ;; *) continue ;; esac   # only year lists
  while IFS= read -r url; do
    case "$url" in http*) : ;; *) continue ;; esac
    rest="${url#http://}"; rest="${rest#https://}"; rest="${rest%/}"
    dir="$RAW/$rest"
    if has_docs "$dir" && [ "$FULL" != "1" ]; then skip=$((skip+1)); continue; fi
    printf "  downloading %s ... " "${rest#www.cespe.unb.br/concursos/}"
    fetch_one "$url"
    if has_docs "$dir"; then
      n=$(find "$dir" -type f ! -iname 'index.html' ! -name '.DS_Store' 2>/dev/null | wc -l | tr -d ' ')
      down=$((down+1)); echo "OK ($n files) -> ${dir#$RAW/}/"
    else
      empty=$((empty+1)); empties="$empties\n  $rest"; echo "EMPTY (dead/moved at source)"
    fi
  done < "$lst"
done

echo
echo "=== PART 2: pre-2002 archive (_antigos/anteriores_2002) ==="
p_ok=0; p_rec=0; p_dead=0; LIST="$RAW/cespe_urls/urls_anteriores_2002_files.txt"
if [ "$SKIP_PRE" = "1" ]; then
  echo "  skipped (SKIP_PRE=1)"
elif ! command -v curl >/dev/null; then
  echo "  curl not found -> skipping pre-2002 (install curl to enable)"
else
  if [ "$REFRESH" = "1" ] || [ ! -s "$LIST" ]; then
    echo "  enumerating file list from Wayback CDX ..."
    CDX="https://web.archive.org/cdx/search/cdx?url=cespe.unb.br/concursos/_antigos/anteriores_2002&matchType=prefix&collapse=urlkey&fl=original&output=text"
    curl -sG "$CDX" \
      | sed -E 's/:80\//\//' | sed -E 's#/concursoS/#/concursos/#g' \
      | grep -iE '/[^/]+\.[a-z0-9]{2,4}$' | grep -viE '\.asp($|\?)|/default\.' \
      | sort -u > "$LIST"
  fi
  echo "  $(grep -c . "$LIST" 2>/dev/null || echo 0) files listed (${LIST#$RAW/})"
  echo "  downloading from live cespe.unb.br (mirroring) ..."
  wget -x --timestamping --tries=3 --wait=0.5 --random-wait --limit-rate=500k \
       -e robots=off -P "$RAW" -i "$LIST" 2>/dev/null || true
  echo "  Wayback fallback for anything missing ..."
  while IFS= read -r url; do
    [ -z "$url" ] && continue
    rel="${url#http://}"; rel="${rel#https://}"; dst="$RAW/$rel"
    if [ -s "$dst" ]; then p_ok=$((p_ok+1)); continue; fi
    mkdir -p "$(dirname "$dst")"
    if wget -q -O "$dst" "https://web.archive.org/web/2id_/$url" && [ -s "$dst" ]; then
      p_rec=$((p_rec+1)); else rm -f "$dst" 2>/dev/null; p_dead=$((p_dead+1)); fi
  done < "$LIST"
fi

echo
echo "===================== SUMMARY ====================="
echo "Part 1 (2002-2019): downloaded $down | skipped $skip | empty $empty"
[ "$empty" -gt 0 ] && printf "  still empty (dead/moved):%b\n" "$empties"
echo "Part 2 (pre-2002) : live/on-disk $p_ok | wayback-recovered $p_rec | dead $p_dead"
echo "Pre-2002 files are mostly .zip -> run 01_unzip_old.sh before 10_pdf_to_text.sh."
echo "Recent Cebraspe -> 0b_/0c_ scripts."
