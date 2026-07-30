#!/bin/bash
# Download CESPE/CEBRASPE archive. Paths are relative to this script's location
# (assumes this file lives in <CEBRASPE>/Code/), so it works on any machine.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
BASE="$CEBRASPE/Raw Data"
cd "$BASE" || { echo "Cannot cd to $BASE"; exit 1; }

# This is the base I use to download
for yr in 2002 2003 2004 2005 2006 2007 2008 2009; do
  wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber \
       --wait=1 --random-wait --limit-rate=500k -i "$BASE/cespe_urls/urls_${yr}.txt"
done

# Some files were not downloaded at all.. Here I'm trying to pull them again.
# Relative paths (from BASE) of the incomplete concurso folders
FOLDERS=(
  "www.cespe.unb.br/concursos/_antigos/2002/TCDF1"
  "www.cespe.unb.br/concursos/_antigos/2002/cbmdf"
  "www.cespe.unb.br/concursos/_antigos/2003/DIPLOMACIA"
  "www.cespe.unb.br/concursos/_antigos/2003/anatel"
  "www.cespe.unb.br/concursos/_antigos/2004/_aneel"
)
URLS=(
  "http://www.cespe.unb.br/concursos/_antigos/2002/TCDF1/"
  "http://www.cespe.unb.br/concursos/_antigos/2002/cbmdf/"
  "http://www.cespe.unb.br/concursos/_antigos/2003/DIPLOMACIA/"
  "http://www.cespe.unb.br/concursos/_antigos/2003/anatel/"
  "http://www.cespe.unb.br/concursos/_antigos/2004/_aneel/"
)

echo "=== Step 1: removing the 5 empty/incomplete folders ==="
for f in "${FOLDERS[@]}"; do
  if [ -d "$f" ]; then echo "  removing $f"; rm -rf "$f"; fi
done

echo; echo "=== Step 2: refetching (no --no-clobber; timestamping instead) ==="
wget --recursive --level=inf --no-parent --ignore-case -e robots=off \
     --timestamping --wait=1 --random-wait --limit-rate=500k "${URLS[@]}"

echo; echo "=== Step 3: verifying results ==="
ok=0; bad=0
for f in "${FOLDERS[@]}"; do
  if [ -d "$f/arquivos" ] && [ -n "$(ls -A "$f/arquivos" 2>/dev/null)" ]; then
    n=$(find "$f/arquivos" -type f | wc -l | tr -d ' ')
    echo "  OK      $f  ($n files in arquivos/)"; ok=$((ok+1))
  else
    echo "  STILL EMPTY  $f  (no arquivos/ - URL may no longer serve content)"; bad=$((bad+1))
  fi
done
echo; echo "Done. Fixed: $ok / 5.  Still empty: $bad."

# (Unused) example to list 2002 PDFs from the Wayback Machine
# curl -sG "http://web.archive.org/cdx/search/cdx" \
#   --data-urlencode "url=cespe.unb.br/concursos*" \
#   --data-urlencode "filter=original:.*/2002/.*\.[Pp][Dd][Ff]$" \
#   --data-urlencode "collapse=urlkey" --data-urlencode "fl=original" \
#   --data-urlencode "output=text" > "$BASE/cespe_urls/cespe_pdfs_2002.txt"
