#!/bin/bash
# Idempotent importer for the CESPE legacy site (cespe.unb.br) — ALL eras.
#
#   PART 1: 2002-2019 concursos, from cespe_urls/urls_YYYY.txt (cover-page recursive wget).
#           Skips concursos that already have docs (metadata check -> NO Dropbox hydration).
#   PART 2: pre-2002 archive (_antigos/anteriores_2002/...). The live index/cover pages
#           return 500, but each concurso's Arquivos/ folder still serves an IIS directory
#           listing. We get the concurso NAMES from the Wayback Machine (CDX) and then
#           recursive-wget each live Arquivos/ listing (complete; Wayback file lists are not).
#           Files are mostly .zip (unzip later with 01_unzip_old.sh).
#
# Everything mirrors into Raw Data/www.cespe.unb.br/...  Re-run anytime (idempotent).
#
# CHOOSE WHICH PARTS TO RUN (default = both):
#   PART=both   (default)   ->  run Part 1 and Part 2
#   PART=1                  ->  run only Part 1 (2002-2019)
#   PART=2                  ->  run only Part 2 (pre-2002)
#   (also accepted as a positional arg, e.g.:  bash 00_import_cespe.sh 1 )
#
# Other options:
#   FULL=1      -> Part 1 also re-runs wget on already-present concursos (top-up partials)
#   REFRESH=1   -> Part 2 re-queries the Wayback CDX list instead of reusing the cached one
# Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
FULL="${FULL:-0}"; REFRESH="${REFRESH:-0}"; PART="${PART:-both}"
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

p_ok=0; p_done=0; p_empty=0; p_empties=""; CLIST="$RAW/cespe_urls/anteriores_2002_concursos.txt"
if [ "$run2" = 1 ]; then
  echo "=== PART 2: pre-2002 archive (_antigos/anteriores_2002) ==="
  if ! command -v curl >/dev/null; then
    echo "  curl not found -> skipping pre-2002 (install curl to enable)"
  else
    # Enumerate the CONCURSO folders from Wayback CDX (dir names are archived even
    # when the individual files are not). We then download each concurso's live
    # Arquivos/ directory listing (IIS), which lists ALL files -- Wayback file lists
    # are incomplete, so we only use it for the folder names.
    if [ "$REFRESH" = "1" ] || [ ! -s "$CLIST" ]; then
      echo "  enumerating concursos from Wayback CDX ..."
      CDX="https://web.archive.org/cdx/search/cdx?url=cespe.unb.br/concursos/_antigos/anteriores_2002&matchType=prefix&collapse=urlkey&fl=original&output=text"
      curl -sG "$CDX" | sed -E 's#/concursoS/#/concursos/#g' \
        | grep -oiE 'anteriores_2002/[0-9]{4}/[^/]+/' | sort -u > "$CLIST"
    fi
    echo "  $(grep -c . "$CLIST" 2>/dev/null || echo 0) concursos (${CLIST#$RAW/})"
    while IFS= read -r cp; do
      [ -z "$cp" ] && continue
      cp="${cp%/}"                                      # anteriores_2002/1997/BACEN_Analista
      arqurl="http://www.cespe.unb.br/concursos/_antigos/${cp}/Arquivos/"
      ldir="$RAW/www.cespe.unb.br/concursos/_antigos/${cp}/Arquivos"
      printf "  %s ... " "${cp#anteriores_2002/}"
      # always top-up: --no-clobber skips files already on disk, fetches the missing ones
      # (a concurso may have only Indice.txt from an earlier run; this completes it)
      wget --recursive --no-parent --level=inf --ignore-case -e robots=off --no-clobber \
           --wait=0.3 --random-wait --limit-rate=500k -P "$RAW" "$arqurl" >/dev/null 2>&1
      if has_docs "$ldir"; then
        n=$(find "$ldir" -type f ! -iname 'index.html' ! -name '.DS_Store' 2>/dev/null | wc -l | tr -d ' ')
        p_ok=$((p_ok+1)); echo "OK ($n files)"
      else
        p_empty=$((p_empty+1)); p_empties="$p_empties\n  $cp"; echo "EMPTY (live dir gone)"
      fi
    done < "$CLIST"
  fi
  echo
fi
echo "===================== SUMMARY (PART=$PART) ====================="
[ "$run1" = 1 ] && { echo "Part 1 (2002-2019): downloaded $down | skipped $skip | empty $empty";
  [ "$empty" -gt 0 ] && printf "  still empty (dead/moved):%b\n" "$empties"; }
[ "$run2" = 1 ] && echo "Part 2 (pre-2002) : concursos with files $p_ok | empty $p_empty"
[ "$run2" = 1 ] && [ "$p_empty" -gt 0 ] && printf "  empty (live dir gone, try Wayback):%b\n" "$p_empties"
[ "$run2" = 1 ] && echo "Pre-2002 files are mostly .zip -> run 01_unzip_old.sh before 10_pdf_to_text.sh."
echo "Recent Cebraspe -> 02_import_cebraspe.sh / 03_import_cebraspe_gaps.sh."
