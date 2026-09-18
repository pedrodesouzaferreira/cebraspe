#!/bin/bash
# Re-download the concursos that are in the URL lists but missing on disk AND still
# live on the legacy cespe.unb.br site (the _antigos/2002-2008 archive).
# Group B (current-path, dead on cespe.unb.br) is NOT handled here -> use the
# Cebraspe scraper / Wayback for those.
#
# Paths are relative to this script (assumes <CEBRASPE>/Code/).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
BASE="$CEBRASPE/Raw Data"
LIST="$BASE/cespe_urls/gaps_A_cespe_antigos.txt"
cd "$BASE" || { echo "cannot cd $BASE"; exit 1; }

echo "Downloading $(grep -c . "$LIST") gap concursos into $BASE ..."
# no --no-clobber so empty/partial stubs get repaired; timestamping keeps server dates
wget --recursive --level=inf --no-parent --ignore-case -e robots=off \
     --timestamping --wait=1 --random-wait --limit-rate=500k -i "$LIST"

echo; echo "=== verify (folder has arquivos with files?) ==="
ok=0; bad=0
while IFS= read -r url; do
  [ -z "$url" ] && continue
  rel="${url#*/concursos/}"; rel="www.cespe.unb.br/concursos/${rel%/}"
  if [ -d "$rel/arquivos" ] && [ -n "$(ls -A "$rel/arquivos" 2>/dev/null)" ]; then
    echo "  OK    ${rel#www.cespe.unb.br/concursos/}"; ok=$((ok+1))
  else
    echo "  EMPTY ${rel#www.cespe.unb.br/concursos/}  (likely dead/moved at source)"; bad=$((bad+1))
  fi
done < "$LIST"
echo; echo "Recovered: $ok  Still empty: $bad  (of $(grep -c . "$LIST"))"
