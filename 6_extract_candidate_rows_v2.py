#!/usr/bin/env python3
"""
Candidate-row extraction (v2) with substantially improved cargo/position recovery.

Key improvements over 3_extract_2006_candidate_rows.py:
  1. Column de-pollution. `pdftotext -layout` merges side-by-side columns onto one
     physical line separated by big whitespace gaps. We split each line on runs of
     >=3 spaces and treat segments independently, so a cargo header like
     "1.1.2 PASTOR EVANGELICO:" is no longer buried next to unrelated column text.
  2. Broader cargo-header detection. Besides an expanded keyword list we accept:
       - numbered headers ending in ':'  (e.g. "1.1.2 PASTOR EVANGELICO:")
       - "CARGO/EMPREGO/AREA/ESPECIALIDADE ...:" labels
       - standalone Title/UPPER lines that are not known section headers
     So unusual cargos (PASTOR EVANGELICO, PADRE CATOLICO, MUSICO, CAPELAO ...) are
     captured even though they are not in any keyword list.
  3. Cargo context is carried forward to the candidate rows that follow the header.

Inputs: a classification queue CSV (default) OR explicit --text-file paths.
Output: candidate_rows_all_raw.csv + a document summary + parser counts.
"""
from __future__ import annotations
import argparse, csv, hashlib, re, sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = DATA_ROOT / "Intermediate" / "classification_all" / "classification_all_result_extraction_queue.csv"
DEFAULT_OUT_DIR = DATA_ROOT / "Intermediate" / "candidate_extraction_all"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

COLSPLIT_RE = re.compile(r"\s{3,}")
INSCRICAO_RE = re.compile(r"\b\d{6,8}\b")

PROSE_WITH_NUMBERS_RE = re.compile(
    r"(?P<inscricao>\b\d{6,8}\b),\s*(?P<nome>[^,/]{3,160}?)\s*,\s*"
    r"(?P<numbers>\d{1,6}(?:[,.]\d{1,4})?(?:\s*,\s*\d{1,6}(?:[,.]\d{1,4})?){0,5})"
    r"(?=\s*/|\s*\.(?:\s|$)|\s*$)")
PROSE_NO_SCORE_RE = re.compile(
    r"(?P<inscricao>\b\d{6,8}\b),\s*(?P<nome>[^,/]{3,160}?)(?=\s*/|\s*\.(?:\s|$)|\s*$)")
FIXED_WIDTH_RE = re.compile(
    r"^(?P<inscricao>\d{6,8})\s+(?P<nome>.+?)\s+(?P<nota>\d{1,4}[,.]\d{1,4})\s+"
    r"(?P<classificacao>\d{1,6})\s+(?P<cargo>.+?)\s*$")

LEVEL_RE = re.compile(r"^N[IÍ]VEL\s+(SUPERIOR|M[EÉ]DIO|FUNDAMENTAL|T[EÉ]CNICO)\b", re.I)
LOCATION_RE = re.compile(r"^(TRE|TSE|TRT|TRF|TJ|MP|PC|PM|SEAD|SEDUC|SES|SEE|OAB)\s*/?\s*[A-Z]{0,3}$")

# Section headers that are NOT cargos (reject list for the generic upper-case rule)
NON_CARGO_HEADER_RE = re.compile(
    r"\b(RESULTADO|RESULTADOS|CLASSIFICA|RELA[CÇ][AÃ]O|CONVOCA|DISPOSI|RECURSOS?|PER[IÍ]CIAS?|"
    r"INSCRI|ANEXO|EDITAL|GABARITO|PROVA|CADERNO|CRONOGRAMA|OBSERVA|ATEN[CÇ][AÃ]O|"
    r"MINIST[EÉ]RIO|SECRETARIA|GOVERNO|FUNDA[CÇ][AÃ]O|UNIVERSIDADE|COMISS[AÃ]O|CENTRO\s+DE\s+SELE|"
    r"CONCURSO|PROCESSO\s+SELETIVO|HOMOLOGA|NOMEA|PORTARIA|COMUNICADO|AVISO)\b", re.I)

# Explicit cargo cue words (help, but not required thanks to the generic rules)
CARGO_CUE_RE = re.compile(
    r"\b(CARGO|EMPREGO|FUN[CÇ][AÃ]O|[AÁ]REA|ESPECIALIDADE|ESPECIALISTA|ANALISTA|T[EÉ]CNICO|"
    r"PROFESSOR|DELEGADO|INVESTIGADOR|ESCRIV|PERITO|JUIZ|PROMOTOR|ADVOGADO|PROCURADOR|AUDITOR|"
    r"AGENTE|ASSISTENTE|SOLDADO|OFICIAL|CABO|SARGENTO|M[UÚ]SICO|CAPEL[AÃ]O|PASTOR|PADRE|"
    r"MEDICO|M[EÉ]DICO|ENFERMEIR|PROFISSIONAL|CADETE|BOMBEIRO|POLICIAL|MOTORISTA|CONDUTOR)\b", re.I)

NUM_HEADER_RE = re.compile(r"^(?P<num>\d+(?:\.\d+){0,3})\s*[-.\)]?\s+(?P<title>.+?)\s*:?\s*$")

def compact(v): return re.sub(r"\s+", " ", v).strip()
def upper_ratio(v):
    letters=[c for c in v if c.isalpha()]
    return sum(c.isupper() for c in letters)/len(letters) if letters else 0.0

def clean_cargo(t):
    return compact(t).strip(" .:-–—").strip()

def detect_cargo_header(seg: str):
    """Return a cargo title if this segment looks like a cargo/position header, else None."""
    s = compact(seg)
    if len(s) < 3 or len(s) > 90:
        return None
    if INSCRICAO_RE.search(s):            # candidate rows carry inscricao numbers
        return None
    if NON_CARGO_HEADER_RE.search(s):
        return None
    # numbered header  "1.1.2 PASTOR EVANGELICO:"
    m = NUM_HEADER_RE.match(s)
    if m:
        title = m.group("title")
        if 3 <= len(title) <= 80 and re.search(r"[A-Za-zÀ-ÿ]", title) and not NON_CARGO_HEADER_RE.search(title):
            if s.rstrip().endswith(":") or upper_ratio(title) >= 0.55 or CARGO_CUE_RE.search(title):
                return clean_cargo(title)
    # explicit "CARGO: xxx" / "EMPREGO N 3: xxx"
    m = re.match(r"^(?:C[OÓ]DIGO\s+\d+\s*[-–]\s*)?(CARGO|EMPREGO|FUN[CÇ][AÃ]O|[AÁ]REA|ESPECIALIDADE)\b[^:]*:\s*(?P<t>.+)$", s, re.I)
    if m and m.group("t"):
        return clean_cargo(m.group("t"))
    # standalone Title/UPPER cargo line (ends with ':' OR is mostly uppercase)
    if (s.endswith(":") or upper_ratio(s) >= 0.6) and CARGO_CUE_RE.search(s):
        return clean_cargo(s)
    # generic uppercase standalone header ending with colon (catch PASTOR/PADRE w/o number)
    if s.endswith(":") and upper_ratio(s[:-1]) >= 0.7 and len(s.split()) <= 8:
        return clean_cargo(s[:-1])
    return None

def plausible_name(v):
    v = compact(v)
    if len(v) < 5 or len(v) > 160: return False
    if re.fullmatch(r"[\d,./\s]+", v): return False
    if re.search(r"\b(Edital|Resultado|Cargo|N[ií]vel|P[aá]gina|CESPE|UnB|Concurso|Minist[eé]rio|Secretaria)\b", v, re.I):
        return False
    return len(v.split()) >= 2

@dataclass
class Row:
    candidate_row_id: str; text_id: str; year: str; concurso_id: str; selection_type: str
    doc_type: str; filename: str; text_path: str; parser: str
    nivel: str; localidade: str; cargo_raw: str
    inscricao: str; nome: str; numbers_raw: str; status_raw: str
    is_sub_judice: int; source_context: str

def mkid(parts): return hashlib.sha1("||".join(parts).encode()).hexdigest()[:20]

def extract_text(qrow: dict) -> tuple[list, dict]:
    path = Path(qrow["text_path"])
    text = path.read_text(encoding="utf-8", errors="replace")
    rows=[]; counts=defaultdict(int)
    nivel=localidade=cargo=""
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = compact(line)
        if not stripped:
            continue
        segments = [seg for seg in COLSPLIT_RE.split(line) if compact(seg)]
        # context updates from segments
        for seg in segments:
            sc = compact(seg)
            if LEVEL_RE.match(sc): nivel = sc; continue
            if LOCATION_RE.match(sc): localidade = sc; continue
            ch = detect_cargo_header(seg)
            if ch: cargo = ch
        # fixed-width on the full line (tables use whitespace as delimiter)
        fw = FIXED_WIDTH_RE.match(stripped)
        if fw and plausible_name(fw.group("nome")) and not re.search(r"Inscri|Nome|Classifica", fw.group("nome"), re.I):
            counts["fixed_width"]+=1
            rows.append(_row(qrow, "fixed_width", nivel, localidade, fw.group("cargo") or cargo,
                             fw.group("inscricao"), fw.group("nome"),
                             f"{fw.group('nota')}, {fw.group('classificacao')}", "", stripped))
            continue
        # prose parsers on each column segment
        for seg in segments:
            segc = compact(seg)
            hits = list(PROSE_WITH_NUMBERS_RE.finditer(segc))
            if hits:
                for m in hits:
                    if not plausible_name(m.group("nome")): continue
                    counts["prose_numbers"]+=1
                    rows.append(_row(qrow,"prose_numbers",nivel,localidade,cargo,
                                     m.group("inscricao"),m.group("nome"),m.group("numbers"),"",segc))
                continue
            for m in PROSE_NO_SCORE_RE.finditer(segc):
                if not plausible_name(m.group("nome")): continue
                counts["prose_no_score"]+=1
                rows.append(_row(qrow,"prose_no_score",nivel,localidade,cargo,
                                 m.group("inscricao"),m.group("nome"),"","",segc))
    # dedupe
    seen={}; 
    for r in rows: seen.setdefault(r.candidate_row_id, r)
    rows=list(seen.values())
    n_reg=int(qrow.get("n_registration_like") or len(INSCRICAO_RE.findall(text)))
    summary=dict(text_id=qrow["text_id"], year=qrow.get("year",""), concurso_id=qrow["concurso_id"],
        selection_type=qrow.get("selection_type",""), doc_type=qrow.get("doc_type",""),
        filename=qrow["filename"], text_path=qrow["text_path"],
        n_registration_like=n_reg, n_rows=len(rows),
        n_with_cargo=sum(1 for r in rows if r.cargo_raw),
        coverage=round(len(rows)/n_reg,4) if n_reg else 0.0,
        needs_review=int((n_reg>=20 and len(rows)==0) or (n_reg>=100 and (len(rows)/n_reg if n_reg else 0)<0.25)))
    return rows, summary

def _row(q,parser,nivel,localidade,cargo,insc,nome,numbers,status,ctx):
    cargo=clean_cargo(cargo)
    rid=mkid([q["text_id"],parser,cargo,insc,compact(nome),numbers,status])
    return Row(rid,q["text_id"],q.get("year",""),q["concurso_id"],q.get("selection_type",""),
        q.get("doc_type",""),q["filename"],q["text_path"],parser,nivel,localidade,cargo,
        insc,compact(nome).strip(" ,.;"),"; ".join(n.strip().replace(",",".") for n in numbers.split(",") if n.strip()),
        status,int(bool(re.search(r"sub\s+judice|liminar|decis.o\s+judicial",ctx,re.I))),compact(ctx)[:400])

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--text-file", action="append", help="Process explicit text files (validation mode).")
    ap.add_argument("--limit", type=int)
    args=ap.parse_args()

    if args.text_file:
        qrows=[]
        for tf in args.text_file:
            p=Path(tf)
            qrows.append(dict(text_id=hashlib.sha1(tf.encode()).hexdigest()[:16], year="", 
                concurso_id=p.parent.parent.name, selection_type="", doc_type="", 
                filename=p.name, text_path=str(p), n_registration_like=""))
    else:
        qrows=list(csv.DictReader(open(args.queue,encoding="utf-8")))
        if args.limit: qrows=qrows[:args.limit]

    all_rows=[]; summaries=[]
    for q in qrows:
        r,s=extract_text(q); all_rows.extend(r); summaries.append(s)

    out=Path(args.out_dir)
    write_csv(out/"candidate_rows_all_raw.csv",[asdict(r) for r in all_rows],list(Row.__dataclass_fields__.keys()))
    write_csv(out/"candidate_extraction_all_document_summary.csv",summaries,list(summaries[0].keys()) if summaries else ["text_id"])
    pc=defaultdict(int)
    for r in all_rows: pc[r.parser]+=1
    write_csv(out/"candidate_extraction_all_parser_counts.csv",[{"parser":k,"n_rows":v} for k,v in sorted(pc.items())],["parser","n_rows"])
    print(f"docs processed : {len(qrows)}")
    print(f"rows extracted : {len(all_rows)}  (with cargo: {sum(1 for r in all_rows if r.cargo_raw)})")
    print(f"parser counts  : {dict(pc)}")
    print(f"output dir     : {out}")

if __name__=="__main__":
    main()
