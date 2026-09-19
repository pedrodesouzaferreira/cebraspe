#!/bin/bash
# Idempotent importer for the CESPE legacy site (cespe.unb.br) — ALL eras.
#
#   PART 1: 2002-2019 concursos, from cespe_urls/urls_YYYY.txt (cover-page recursive wget).
#           Skips concursos that already have docs (metadata check -> NO Dropbox hydration).
#   PART 2: pre-2002 archive (_antigos/anteriores_2002/...). The root / year / concurso
#           dirs all serve IIS directory listings, so a SINGLE recursive wget mirrors every
#           year, concurso and its files -- handles both 'Arquivo' and 'Arquivos' subfolder
#           names and needs no Wayback. Files are mostly .zip (unzip with 01_unzip_old.sh).
#
# Everything mirrors into Raw Data/www.cespe.unb.br/...  Re-run anytime (idempotent).
#
# CHOOSE WHICH PARTS TO RUN (default = both):
#   PART=both (default) -> both ;  PART=1 -> only 2002-2019 ;  PART=2 -> only pre-2002
#   (also as a positional arg, e.g.:  bash 00_import_cespe.sh 1 )
#   FULL=1  -> Part 1 also re-runs wget on already-present concursos (top-up partials)
# Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
FULL="${FULL:-0}"; PART="${PART:-both}"
case "${1:-}" in 1|2|both) PART="$1" ;; "") : ;; *) echo "uso: [PART=both|1|2] $0 [1|2|both]"; exit 2 ;; esac
run1=0; run2=0
case "$PART" in both) run1=1; run2=1 ;; 1) run1=1 ;; 2) run2=1 ;; *) echo "PART invalido: $PART"; exit 2 ;; esac
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

down=0; skip=0; empty=0; empties=""
if [ "$run1" = 1 ]; then
  echo "=== PART 1: 2002-2019 (cover pages) ==="
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
fi

p_conc=0; p_files=0
if [ "$run2" = 1 ]; then
  echo "=== PART 2: pre-2002 archive (_antigos/anteriores_2002) ==="
  echo "  mirroring live IIS directory listings (all years/concursos) ..."
  ROOT="http://www.cespe.unb.br/concursos/_antigos/anteriores_2002/"
  # single recursive crawl: root -> years -> concursos -> Arquivo(s)/ -> files.
  # --timestamping keeps it re-runnable (re-reads listings, skips unchanged files).
  wget --recursive --no-parent --level=inf -e robots=off --timestamping \
       --wait=0.3 --random-wait --limit-rate=500k -P "$RAW" "$ROOT" >/dev/null 2>&1 || true
  base2="$RAW/www.cespe.unb.br/concursos/_antigos/anteriores_2002"
  p_conc=$(find "$base2" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | wc -l | tr -d ' ')
  p_files=$(find "$base2" -type f ! -iname 'index.html' ! -name '.DS_Store' 2>/dev/null | wc -l | tr -d ' ')
  echo "  concursos: $p_conc | files on disk: $p_files"
  echo
fi

echo "===================== SUMMARY (PART=$PART) ====================="
[ "$run1" = 1 ] && { echo "Part 1 (2002-2019): downloaded $down | skipped $skip | empty $empty";
  [ "$empty" -gt 0 ] && printf "  still empty (dead/moved):%b\n" "$empties"; }
[ "$run2" = 1 ] && echo "Part 2 (pre-2002) : concursos $p_conc | files on disk $p_files"
[ "$run2" = 1 ] && echo "Pre-2002 files are mostly .zip -> run 01_unzip_old.sh before 10_pdf_to_text.sh."
echo "Recent Cebraspe -> 02_import_cebraspe.sh / 03_import_cebraspe_gaps.sh."
