#!/bin/bash
# Download recent CEBRASPE concursos (fase "encerrado") from the modern site.
#
# Discovery uses the site's JSON APIs; files come from the CDN:
#   list  : https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado
#   detail: https://apis.cebraspe.org.br/cebraspe/eventos/<eventoURL>
#   file  : https://cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/<nomeArquivo>
#
# Phase 1 (python/urllib): build the file URL list + an index TSV.
# Phase 2 (wget): mirror-download into Raw Data/cdn.cebraspe.org.br/concursos/...
# Idempotent: wget -nc skips files already on disk. Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
OUTLIST="$RAW/cespe_urls/urls_cebraspe_encerrado.txt"
INDEX="$RAW/cespe_urls/cebraspe_encerrado_index.tsv"
for c in python3 wget; do command -v $c >/dev/null || { echo "ERROR: $c not found"; exit 1; }; done
mkdir -p "$(dirname "$OUTLIST")"

echo "[1/2] Discovering concursos + files via API ..."
python3 - "$OUTLIST" "$INDEX" << 'PY'
import sys, json, time, urllib.request, urllib.parse
OUTLIST, INDEX = sys.argv[1], sys.argv[2]
UA={"User-Agent":"Mozilla/5.0"}
CDN="https://cdn.cebraspe.org.br/concursos"
def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(1.5)
    return None
lst = get("https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado")
eventos = lst[0]["eventos"] if lst else []
print(f"    {len(eventos)} concursos listed")
urls=[]; rows=[]
for i,ev in enumerate(eventos,1):
    url=ev.get("eventoURL"); ano=ev.get("eventoAno") or ""
    nome=(ev.get("eventoNomeAbreviado") or "").replace("\t"," ")
    if not url: continue
    d=get(f"https://apis.cebraspe.org.br/cebraspe/eventos/{urllib.parse.quote(url)}")
    files=[]
    if d:
        for key in ("arquivosEdital","arquivosGabarito"):
            for a in (d.get(key) or []):
                nm=a.get("nomeArquivo")
                if nm: files.append(nm)
    seen=set()
    for nm in files:
        if nm in seen: continue
        seen.add(nm)
        urls.append(f"{CDN}/{urllib.parse.quote(url)}/arquivos/{urllib.parse.quote(nm)}")
    rows.append(f"{url}\t{ano}\t{nome}\t{len(seen)}")
    if i%25==0: print(f"    ...{i}/{len(eventos)} concursos processed")
    time.sleep(0.15)
open(OUTLIST,"w").write("\n".join(urls)+"\n")
open(INDEX,"w").write("eventoURL\tano\tnome\tn_files\n"+"\n".join(rows)+"\n")
print(f"    files to download: {len(urls)}  ->  {OUTLIST}")
print(f"    index: {INDEX}")
PY

echo "[2/2] Downloading files from CDN (mirroring tree) ..."
wget -x -nc -e robots=off -U "Mozilla/5.0" --tries=3 --timeout=30 \
     --wait=0.3 --random-wait --limit-rate=800k -P "$RAW" -i "$OUTLIST" 2>&1 \
  | grep -Ei 'saved|ERROR|404|already there' | tail -0 || true
echo "Done. Files under: $RAW/cdn.cebraspe.org.br/concursos/"
echo "Tip: to convert, add \"\$RAW/cdn.cebraspe.org.br\" to SRC_ROOTS in 1_pdf_to_text.sh."
