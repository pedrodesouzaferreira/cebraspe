#!/usr/bin/env python3
"""
Year-agnostic classification of the whole CEBRASPE/CESPE text corpus.

Generalizes 2_classify_2006_texts.py to every year folder under
`Raw Data/text/` (2002..2008 and the `outros` bucket of newer concursos).

Adds a CONCURSO-LEVEL `selection_type`:
  - public_job                 (concurso publico for cargo/emprego)
  - scholarship_exchange       (bolsa-premio, intercambio, exchange)
  - medical_residency          (residencia medica/multiprofissional/uniprofissional)
  - revalidation_proficiency_cert  (revalidacao de diploma, proficiencia, OAB, vestibular, certificacao)
  - other

selection_type is decided per concurso (from the concurso id + the opening
notice / aggregated head text), NOT per individual filename, because tokens like
"REVALIDACAO DE MATRICULA" show up inside ordinary police concursos.

Outputs (to Intermediate/classification_all/):
  classification_all_editable.csv            one row per text file
  classification_all_counts.csv              doc_type x n_files
  selection_type_by_concurso.csv             REVIEWABLE concurso -> selection_type (+ override col)
  classification_all_result_extraction_queue.csv   result-like docs for extractor
"""
from __future__ import annotations

import argparse, csv, hashlib, re, sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]           # .../CEBRASPE
DEFAULT_TEXT_DIR = DATA_ROOT / "Raw Data" / "text"
CONCURSOS_DIR = DATA_ROOT / "Raw Data" / "www.cespe.unb.br" / "concursos"
DEFAULT_OUT_DIR = DATA_ROOT / "Intermediate" / "classification_all"

MAXCHARS = 400000
ARCHIVE_YEARS = {"2002", "2003", "2004", "2005", "2006", "2007", "2008"}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# ----------------------------- doc_type rules -----------------------------
DOC_TYPES = ["opening_notice","final_result","provisional_result","intermediate_result",
    "convocation","locations","demand","answer_key","exam","erratum","appeals",
    "communication","manual_or_regulation","administrative","other"]

def rx(p): return re.compile(p, re.I | re.M)

@dataclass
class Rule:
    doc_type: str; pattern: "re.Pattern[str]"; weight: int; evidence: str

FILENAME_RULES = [
    Rule("answer_key", rx(r"(^|[^A-Z0-9])(gab|gabarito|gabaritos)([^A-Z0-9]|$)"), 12, "fn answer-key"),
    Rule("exam", rx(r"(^|[^A-Z0-9])(prova|caderno|cargo\s?\d+)([^A-Z0-9]|$)"), 8, "fn exam"),
    Rule("demand", rx(r"(^|[^A-Z0-9])(demanda|quantitativos?\s+inscritos|inscritos)([^A-Z0-9]|$)"), 12, "fn demand"),
    Rule("opening_notice", rx(r"(^|[^A-Z0-9])(abt|abertura|ed\s?1\s|edital\s?1\s)([^A-Z0-9]|$)"), 7, "fn opening"),
    Rule("final_result", rx(r"(^|[^A-Z0-9])(res\s?fin|resultado\s?final|fin\s?conc|homolog)([^A-Z0-9]|$)"), 9, "fn final"),
    Rule("provisional_result", rx(r"(^|[^A-Z0-9])(res\s?prov|resultado\s?provis|provisorio|provis.rio)([^A-Z0-9]|$)"), 8, "fn provisional"),
    Rule("convocation", rx(r"(^|[^A-Z0-9])(conv|convoc|convocacao|curso\s?de\s?formacao|matricula|nomea)([^A-Z0-9]|$)"), 7, "fn convocation"),
    Rule("locations", rx(r"(^|[^A-Z0-9])(locais?|horario|local\s?e\s?horario)([^A-Z0-9]|$)"), 8, "fn locations"),
    Rule("erratum", rx(r"(^|[^A-Z0-9])(ret|retif|retificacao|errata|erro\s?material|sub\s?judice|judice|liminar)([^A-Z0-9]|$)"), 7, "fn erratum"),
    Rule("appeals", rx(r"(^|[^A-Z0-9])(recurso|recursos|anulacao|razoes)([^A-Z0-9]|$)"), 7, "fn appeals"),
    Rule("communication", rx(r"(^|[^A-Z0-9])(comunicado|aviso|nota|suspensao|cancelamento|prorrogacao)([^A-Z0-9]|$)"), 6, "fn communication"),
    Rule("manual_or_regulation", rx(r"(^|[^A-Z0-9])(manual|regulamento|resolucao|portaria|instrucao|anexo)([^A-Z0-9]|$)"), 7, "fn manual"),
]
TEXT_RULES = [
    Rule("demand", rx(r"DEMANDA\s+DE\s+CANDIDATOS\s+POR\s+VAGA|INSCRITOS\s+VAGAS\s+DEMANDA"), 18, "demand table"),
    Rule("answer_key", rx(r"GABARITOS?\s+(?:OFICIAIS?\s+)?(?:DEFINITIVOS?|PRELIMINARES?)|JUSTIFICATIVAS?\s+DE\s+ALTERA..O\s+DE\s+GABARITO|Gabarito\s+oficial"), 18, "answer-key phrase"),
    Rule("exam", rx(r"Julgue\s+os\s+itens|De acordo com o comando a que cada um dos itens|Caderno\s+[A-Z0-9]|Folha de respostas|Cargo\s+\d+:"), 14, "exam phrase"),
    Rule("opening_notice", rx(r"torna\s+p[uú]blic[ao]s?\s+a\s+(?:abertura|realiza..o)|abertura\s+de\s+inscri..es|DAS\s+INSCRI..ES|remunera..o\s+inicial|DOS\s+CARGOS"), 14, "opening phrase"),
    Rule("final_result", rx(r"resultado\s+final\s+no\s+concurso|resultado\s+final\s+do\s+concurso|resultado\s+final\s*[-–]|classifica..o\s+final\s+no\s+concurso|resultado\s+final\s+na"), 15, "final phrase"),
    Rule("provisional_result", rx(r"resultado\s+provis[oó]rio|resultado\s+prov\.?|res\.?\s+prov"), 14, "provisional phrase"),
    Rule("intermediate_result", rx(r"resultado\s+(?:final|provis[oó]rio)\s+(?:da|das|do|dos|na|nas|no|nos)\s+(?:prova|avalia..o|per.cia|exame|investiga..o|sindic.ncia|t.tulos|capacidade|aptid.o|oral|discursiva|pr.tica)"), 11, "stage-result phrase"),
    Rule("convocation", rx(r"convoca(?:m|dos?|..o|r)?\s+(?:os\s+)?candidatos|convoca..o\s+para|curso\s+de\s+forma..o|matr.cula|nomea..o"), 11, "convocation phrase"),
    Rule("locations", rx(r"locais?\s+e\s+hor[aá]rios?|local\s+e\s+hor[aá]rio|locais?\s+de\s+provas?"), 12, "locations phrase"),
    Rule("erratum", rx(r"retifica(?:m|r|..o)|errata|erro\s+material|sub\s+judice|liminar|decis.o\s+judicial|suspens.o"), 10, "erratum phrase"),
    Rule("appeals", rx(r"recurso|recursos|raz[oõ]es\s+para\s+(?:anula..o|manuten..o)|anula..o\s+de\s+quest.o|altera..o\s+de\s+gabarito"), 9, "appeals phrase"),
    Rule("communication", rx(r"comunicado|aviso|nota\s+explicativa|prorroga..o|cancelamento"), 8, "communication phrase"),
    Rule("manual_or_regulation", rx(r"manual\s+do\s+candidato|manual\s+do\s+aluno|regulamento|resolu..o\s+n|portaria\s+n|instru..o\s+normativa"), 10, "manual phrase"),
    Rule("administrative", rx(r"ata\s+de\s+sess.o|termo\s+aditivo|despacho|publica..o\s+-\s+concurso"), 8, "administrative phrase"),
]

REGISTRATION_RE = re.compile(r"\b\d{6,8}\b")
SCORE_RANK_RE = re.compile(r"\b\d{6,8}\b,\s*[^,/]{5,120}?,\s*\d{1,3}[,.]\d{1,2},\s*\d+\b")
CANDIDATE_TABLE_HEADER_RE = rx(r"inscri..o\s+nome|n.mero\s+de\s+inscri..o,\s+nome|nome\s+do\s+candidato")
RESULT_PHRASE_RE = rx(r"resultado\s+(?:final|provis[oó]rio)|classifica..o\s+final")

def normalize(t): return t.replace("_"," ").replace("-"," ").replace("–"," ")

def score_document(filename, text):
    scores = {d:0 for d in DOC_TYPES}; evidence=[]
    fn = normalize(filename); head = normalize(text[:15000])
    for r in FILENAME_RULES:
        if r.pattern.search(fn): scores[r.doc_type]+=r.weight; evidence.append(r.evidence)
    for r in TEXT_RULES:
        if r.pattern.search(head): scores[r.doc_type]+=r.weight; evidence.append(r.evidence)
    n_reg = len(REGISTRATION_RE.findall(text)); n_sr = len(SCORE_RANK_RE.findall(text))
    if n_sr >= 10: scores["final_result"]+=7; evidence.append("many score/rank rows")
    elif n_sr >= 2: scores["intermediate_result"]+=4; evidence.append("some score/rank rows")
    elif n_reg >= 20 and RESULT_PHRASE_RE.search(head): scores["intermediate_result"]+=5; evidence.append("many regs + result phrase")
    elif n_reg >= 50 and not scores["exam"]: scores["intermediate_result"]+=2; evidence.append("many reg-like numbers")
    if scores["locations"] and n_sr==0: scores["locations"]+=4
    if scores["opening_notice"] and max(scores["demand"],scores["answer_key"],scores["exam"],scores["final_result"])>=14:
        scores["opening_notice"]=max(0,scores["opening_notice"]-5)
    return scores, evidence, n_reg, n_sr

def choose_label(scores, text_head_has_result, n_reg):
    ranked = sorted(scores.items(), key=lambda i:(-i[1], i[0]))
    best,bs = ranked[0]; second = ranked[1][1] if len(ranked)>1 else 0
    if bs==0: return "other", 0.0, 1
    conf = min(0.99, 0.45 + bs/35 + max(0,bs-second)/25)
    ambiguous = (bs-second)<=3 and second>=8
    needs = int(best=="other" or conf<0.72 or ambiguous)
    if best in {"communication","erratum","administrative","other"} and n_reg>=10: needs=1
    return best, round(conf,3), needs

# --------------------------- selection_type -------------------------------
# Concurso-level. Ordered priority; first strong hit wins.
SEL_ID_RULES = [
    ("scholarship_exchange", re.compile(r"BOLSA|INTERCAMB|EXCHANGE", re.I)),
    ("medical_residency",   re.compile(r"RESIDENC|MULTIPROF|UNIPROF|PROSAUDE", re.I)),
    ("revalidation_proficiency_cert", re.compile(r"REVALIDA|PROFICIENC|OAB|VESTIBULAR|\bVEST|CERTIFICAC", re.I)),
]
SEL_TEXT_RULES = [
    ("scholarship_exchange", re.compile(r"bolsas?[\s\-]*pr[eê]mio|programa\s+de\s+interc[aâ]mbio|bolsa\s+de\s+estudos", re.I)),
    ("medical_residency",   re.compile(r"resid[eê]ncia\s+m[eé]dica|resid[eê]ncia\s+multiprofissional|resid[eê]ncia\s+em\s+[aá]rea|programa\s+de\s+resid[eê]ncia", re.I)),
    ("revalidation_proficiency_cert", re.compile(r"revalida..o\s+de\s+diploma|exame\s+de\s+profici[eê]ncia|exame\s+de\s+ordem|processo\s+seletivo.*vestibular|exame\s+vestibular|certifica..o\s+de\s+conhecimentos", re.I)),
]
JOB_TEXT_RE = re.compile(r"concurso\s+p[uú]blico|provimento\s+de\s+(?:cargos?|vagas?)|do[s]?\s+cargos?|emprego\s+p[uú]blico|remunera..o|vagas?", re.I)
RESID_JURIDICA_RE = re.compile(r"RESIDENC.*JURIDIC", re.I)

def concurso_selection_type(concurso_id, id_blob, opening_text):
    # id_blob = concurso_id normalized; opening_text = best head text
    # Special-case: residencia juridica (legal traineeship) is not medical.
    if RESID_JURIDICA_RE.search(concurso_id):
        return "other", "id: residencia juridica (legal traineeship)"
    for stype, pat in SEL_ID_RULES:
        m = pat.search(concurso_id)
        if m: return stype, f"id token: {m.group(0)}"
    for stype, pat in SEL_TEXT_RULES:
        m = pat.search(opening_text)
        if m: return stype, f"text: {m.group(0)[:40]}"
    if JOB_TEXT_RE.search(opening_text): return "public_job", "text: job signal"
    return "other", "no strong signal"

# ------------------------------ IO helpers --------------------------------
def stable_id(s): return hashlib.sha1(str(s).encode()).hexdigest()[:16]

def year_and_source(text_path: Path, text_dir: Path):
    """Derive (year, concurso_id, source_pdf_path) from a text file path.

    Supports BOTH layouts so it works before/after the mirror migration:
      MIRROR (new): text/www.cespe.unb.br/concursos/_antigos/<year>/<concurso>/...
                    text/www.cespe.unb.br/concursos/<concurso>/...   (current)
      OLD:          text/<year>/<concurso>/...    (year in 2002..2008)
                    text/outros/<concurso>/...    (current)
    """
    rel = text_path.relative_to(text_dir)
    parts = list(rel.parts)
    rel_wo_txt = Path(str(rel)[:-4]) if str(rel).lower().endswith(".txt") else rel

    def yr_from(name):
        m = re.search(r"(19|20)\d{2}", name); return m.group(0) if m else ""

    # ---- MIRROR layout (path contains 'concursos') ----
    if "concursos" in parts:
        i = parts.index("concursos")
        after = parts[i + 1:]
        src = CONCURSOS_DIR / Path(*rel_wo_txt.parts[i + 1:])
        if after and after[0] == "_antigos" and len(after) >= 3:
            return after[1], after[2], str(src), ""
        concurso_id = after[0] if after else ""
        return yr_from(concurso_id), concurso_id, str(src), ""

    # ---- OLD layout ----
    top = parts[0]
    concurso_id = parts[1] if len(parts) > 1 else parts[0]
    if top in ARCHIVE_YEARS:
        return top, concurso_id, str(CONCURSOS_DIR / "_antigos" / rel_wo_txt), ""
    if top == "outros":
        src = CONCURSOS_DIR / Path(*rel_wo_txt.parts[1:])
        return yr_from(concurso_id), concurso_id, str(src), ""
    return "", concurso_id, str(CONCURSOS_DIR / rel_wo_txt), ""

def compact(t, n=700): return re.sub(r"\s+"," ",t).strip()[:n]

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-dir", default=str(DEFAULT_TEXT_DIR))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurso", action="append", help="Restrict to these concurso folder names.")
    args = ap.parse_args()
    text_dir = Path(args.text_dir); out_dir = Path(args.out_dir)

    paths = sorted(p for p in text_dir.rglob("*.txt") if p.is_file())
    if args.concurso:
        want=set(args.concurso)
        paths=[p for p in paths if any(part in want for part in p.relative_to(text_dir).parts)]
    if args.limit: paths = paths[:args.limit]

    docs = []                     # per-file dict
    concurso_head = {}            # (year,cid) -> {"opening":..., "longest":..., "llen":...}
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace")[:MAXCHARS]
        year, cid, src, src_exists = year_and_source(p, text_dir)
        scores, evidence, n_reg, n_sr = score_document(p.name, text)
        label, conf, needs = choose_label(scores, bool(RESULT_PHRASE_RE.search(text[:20000])), n_reg)
        rec = dict(
            text_id=stable_id(p.relative_to(text_dir)),
            year=year, concurso_id=cid,
            text_rel_path=str(p.relative_to(text_dir)),
            text_path=str(p), filename=p.name,
            original_pdf_path=src, original_pdf_exists=src_exists,
            doc_type=label, confidence=conf, needs_review=needs,
            n_registration_like=n_reg, n_score_rank_like=n_sr,
            has_result_phrase=int(bool(RESULT_PHRASE_RE.search(text[:20000]))),
            has_candidate_header=int(bool(CANDIDATE_TABLE_HEADER_RE.search(text[:20000]))),
            evidence="; ".join(dict.fromkeys(evidence)),
            head_snippet=compact(text[:1500]),
        )
        docs.append(rec)
        key = (year, cid)
        info = concurso_head.setdefault(key, {"opening": "", "longest": "", "llen": -1, "n": 0})
        info["n"] += 1
        if label == "opening_notice" and not info["opening"]:
            info["opening"] = text[:6000]
        if len(text) > info["llen"]:
            info["llen"] = len(text); info["longest"] = text[:6000]

    # selection_type per concurso
    sel = {}
    sel_rows = []
    for (year, cid), info in sorted(concurso_head.items()):
        id_norm = cid.upper()
        opening = info["opening"] or info["longest"]
        stype, ev = concurso_selection_type(id_norm, id_norm, opening)
        sel[(year, cid)] = stype
        sel_rows.append(dict(year=year, concurso_id=cid, n_docs=info["n"],
                             selection_type=stype, selection_type_evidence=ev,
                             selection_type_override=""))
    for rec in docs:
        rec["selection_type"] = sel[(rec["year"], rec["concurso_id"])]

    doc_fields = ["text_id","year","concurso_id","selection_type","doc_type","confidence",
        "needs_review","n_registration_like","n_score_rank_like","has_result_phrase",
        "has_candidate_header","text_rel_path","text_path","original_pdf_path",
        "original_pdf_exists","filename","evidence","head_snippet"]
    write_csv(out_dir/"classification_all_editable.csv", docs, doc_fields)

    write_csv(out_dir/"selection_type_by_concurso.csv", sel_rows,
        ["year","concurso_id","n_docs","selection_type","selection_type_evidence","selection_type_override"])

    counts = defaultdict(int); scounts = defaultdict(int)
    for r in docs: counts[r["doc_type"]]+=1
    for r in sel_rows: scounts[r["selection_type"]]+=1
    write_csv(out_dir/"classification_all_counts.csv",
        [{"doc_type":d,"n_files":counts[d]} for d in DOC_TYPES if counts[d]],
        ["doc_type","n_files"])
    write_csv(out_dir/"selection_type_counts.csv",
        [{"selection_type":k,"n_concursos":v} for k,v in sorted(scounts.items(), key=lambda x:-x[1])],
        ["selection_type","n_concursos"])

    q = [r for r in docs if r["doc_type"] in {"final_result","provisional_result","intermediate_result"}
         or (r["n_registration_like"]>=20 and r["has_result_phrase"])]
    q.sort(key=lambda r:(r["doc_type"]!="final_result", -r["n_score_rank_like"], -r["n_registration_like"], r["year"], r["concurso_id"], r["filename"]))
    write_csv(out_dir/"classification_all_result_extraction_queue.csv", q, doc_fields)

    print(f"text files classified : {len(docs)}")
    print(f"concursos              : {len(sel_rows)}")
    print(f"result extraction queue: {len(q)}")
    print("selection_type breakdown:", dict(sorted(scounts.items(), key=lambda x:-x[1])))
    print(f"output dir             : {out_dir}")

if __name__ == "__main__":
    main()
