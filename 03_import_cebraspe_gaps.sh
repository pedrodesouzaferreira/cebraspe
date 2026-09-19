#!/bin/bash
# Recover CEBRASPE concursos that 02_import_cebraspe.sh couldn't get because their
# detail API returns HTTP 500 (or lists zero files). Files still exist on the live
# CDN; we enumerate via Wayback (CDX) and download from the live CDN, falling back
# to the Wayback snapshot per file. All logic in Python (handles encoding/paths).
# Run locally. Idempotent (skips files already on disk).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }

python3 - "$RAW" << 'PY'
import sys, os, re, json, time, urllib.request, urllib.parse
RAW=sys.argv[1]
CDNROOT=os.path.join(RAW,"cdn.cebraspe.org.br","concursos")
REPORT=os.path.join(RAW,"cespe_urls","cebraspe_gaps_report.tsv")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
UA={"User-Agent":"Mozilla/5.0"}

def fetch(url, timeout=40):
    req=urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def get_text(url, tries=3):
    for _ in range(tries):
        try: return fetch(url).decode("utf-8","replace")
        except Exception: time.sleep(1.0)
    return None

# 1) list -> gaps (concursos with no non-empty local folder)
lst=json.loads(get_text("https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado") or "[]")
eventos=lst[0]["eventos"] if lst else []
def has_local(u):
    d=os.path.join(CDNROOT,u,"arquivos")
    return os.path.isdir(d) and any(os.scandir(d))
gaps=[ev["eventoURL"] for ev in eventos if ev.get("eventoURL") and not has_local(ev["eventoURL"])]
print(f"[1/2] {len(eventos)} listed, {len(gaps)} gaps to recover")

def enc(url):  # percent-encode path (leave existing %xx and / intact)
    p=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(p.path, safe="/%"),"",""))

def save(file_url):
    """file_url: original (maybe raw) CDN url. Returns 'live'|'wayback'|'dead'|'skip'."""
    path=urllib.parse.unquote(urllib.parse.urlsplit(file_url).path)  # /concursos/.../x.pdf (decoded)
    dst=os.path.join(RAW,"cdn.cebraspe.org.br",path.lstrip("/"))
    if os.path.exists(dst) and os.path.getsize(dst)>0: return "skip"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    live="https://cdn.cebraspe.org.br"+urllib.parse.urlsplit(enc(file_url)).path
    for src in (live, "https://web.archive.org/web/2id_/"+file_url):
        try:
            data=fetch(src)
            if data and len(data)>0:
                open(dst,"wb").write(data)
                return "live" if src==live else "wayback"
        except Exception: pass
    return "dead"

# 2) per gap: CDX enumerate -> download
rows=[]; tot=dict(live=0,wayback=0,dead=0,skip=0)
for i,u in enumerate(gaps,1):
    cdx=("https://web.archive.org/cdx/search/cdx?url="
         +urllib.parse.quote(f"cdn.cebraspe.org.br/concursos/{u}/arquivos")
         +"&matchType=prefix&fl=original&collapse=urlkey&output=text")
    txt=get_text(cdx) or ""
    files=sorted({ln.strip() for ln in txt.splitlines()
                  if ln.strip() and re.search(r"/[^/]+\.[A-Za-z0-9]{2,4}$", ln)})
    got=0
    for f in files:
        r=save(f); tot[r]+=1
        if r in ("live","wayback","skip"): got+=1
        time.sleep(0.05)
    rows.append(f"{u}\t{len(files)}\t{got}")
    print(f"    [{i}/{len(gaps)}] {u}: {len(files)} files, {got} ok")
    time.sleep(0.2)
open(REPORT,"w").write("eventoURL\tn_found\tn_ok\n"+"\n".join(rows)+"\n")
print(f"\n[2/2] done. live={tot['live']} wayback={tot['wayback']} skip={tot['skip']} dead={tot['dead']}")
print(f"report -> {REPORT}")
empty=[r.split(chr(9))[0] for r in rows if r.endswith('\t0\t0')]
if empty: print(f"genuinely empty (no files on CDN/Wayback): {', '.join(empty)}")
PY
