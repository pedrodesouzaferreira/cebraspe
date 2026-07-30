# This is the base I use to download
cd "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2002.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2003.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2004.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2005.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2006.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2007.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2008.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2009.txt"

# Some files were not downloaded at all.. Here I'm trying to pull them again. 
set -u
 
BASE="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data"
cd "$BASE" || { echo "Cannot cd to $BASE"; exit 1; }
 
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
  if [ -d "$f" ]; then
    echo "  removing $f"
    rm -rf "$f"
  fi
done
 
echo
echo "=== Step 2: refetching (no --no-clobber; timestamping instead) ==="
wget --recursive --level=inf --no-parent --ignore-case -e robots=off \
     --timestamping --wait=1 --random-wait --limit-rate=500k \
     "${URLS[@]}"
 
echo
echo "=== Step 3: verifying results ==="
ok=0; bad=0
for f in "${FOLDERS[@]}"; do
  if [ -d "$f/arquivos" ] && [ -n "$(ls -A "$f/arquivos" 2>/dev/null)" ]; then
    n=$(find "$f/arquivos" -type f | wc -l | tr -d ' ')
    echo "  OK      $f  ($n files in arquivos/)"
    ok=$((ok+1))
  else
    echo "  STILL EMPTY  $f  (no arquivos/ - URL may no longer serve content)"
    bad=$((bad+1))
  fi
done
 
echo
echo "Done. Fixed: $ok / 5.  Still empty: $bad."
if [ "$bad" -gt 0 ]; then
  echo "Any 'STILL EMPTY' folders likely no longer exist at the old cespe.unb.br"
  echo "address (the site moved to cebraspe.org.br) rather than being a download error."
fi
 

# This is a script I never used to download from web archive
curl -sG "http://web.archive.org/cdx/search/cdx" \
  --data-urlencode "url=cespe.unb.br/concursos*" \
  --data-urlencode "filter=original:.*/2002/.*\.[Pp][Dd][Ff]$" \
  --data-urlencode "collapse=urlkey" \
  --data-urlencode "fl=original" \
  --data-urlencode "output=text" \
  > ~/Downloads/cespe_pdfs_2002.txt
wc -l ~/Downloads/cespe_pdfs_2002.txt
head -30 ~/Downloads/cespe_pdfs_2002.txt