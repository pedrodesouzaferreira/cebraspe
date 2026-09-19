#!/bin/bash
# Idempotent importer for the CESPE/CEBRASPE legacy site (cespe.unb.br).
# Reads every cespe_urls/urls_YYYY.txt (2002-2019), and for EACH concurso cover page:
#   - checks if its folder already has documents (metadata only -> NO Dropbox hydration)
#   - if empty/missing, downloads it (wget --recursive, file-level --no-clobber)
# Re-run anytime: already-downloaded concursos are skipped; gaps are filled.
# This replaces the old per-year loop AND redownload_gaps.sh.
#
#   FULL=1  -> also run wget on already-present concursos (file-level top-up of partials)
# Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
FULL="${FULL:-0}"
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
for lst in cespe_urls/urls_*.txt; do
  base="$(basename "$lst")"
  case "$base" in urls_[0-9][0-9][0-9][0-9].txt) : ;; *) continue ;; esac   # only year lists
  while IFS= read -r url; do
    case "$url" in http*) : ;; *) continue ;; esac
    rest="${url#http://}"; rest="${rest#https://}"; rest="${rest%/}"        # www.cespe.unb.br/concursos/...
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
echo "Downloaded/updated : $down"
echo "Skipped (had docs) : $skip"
echo "Still empty (dead/moved at source): $empty"
[ "$empty" -gt 0 ] && printf "%b\n" "$empties"
echo
echo "Note: pre-2002 -> 2_download_anteriores_2002.sh ; recent Cebraspe -> 0b_/0c_ scripts."
