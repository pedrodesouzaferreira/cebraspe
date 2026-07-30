#!/usr/bin/env python3
"""
Collapse v2 raw candidate rows to the EARLIEST result per applicant, all years.

Generalizes 4_select_earliest_2006_candidate_rows.py:
  - reads candidate_rows_all_raw.csv (any year),
  - keeps the selection_type flag,
  - one row per application key using transparent document priority:
      stage_rank (more preliminary first) -> edital number -> doc date -> filename.
"""
from __future__ import annotations
import argparse, csv, hashlib, re, sys, unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = DATA_ROOT / "Intermediate" / "candidate_extraction_all" / "candidate_rows_all_raw.csv"
DEFAULT_OUT = DATA_ROOT / "Intermediate" / "candidate_extraction_all"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

MONTHS={"janeiro":"01","fevereiro":"02","marco":"03","março":"03","abril":"04","maio":"05",
"junho":"06","julho":"07","agosto":"08","setembro":"09","outubro":"10","novembro":"11","dezembro":"12"}

def strip_accents(v): return "".join(c for c in unicodedata.normalize("NFKD",v) if not unicodedata.combining(c))
def norm_key(v):
    v=strip_accents(v or "").upper(); v=re.sub(r"[^A-Z0-9]+"," ",v); return re.sub(r"\s+"," ",v).strip()
def sid(parts): return hashlib.sha1("||".join(parts).encode()).hexdigest()[:20]
def read_head(path,n=8000):
    try: return Path(path).read_text(encoding="utf-8",errors="replace")[:n]
    except OSError: return ""

def parse_edital(filename,head):
    cands=[]; sp=f"{filename}\n{head[:2500]}"
    for pat in [r"EDITAL\s+COMPLEMENTAR\s+N?[.º°]?\s*(\d+)",r"ED(?:ITAL)?[_\s-]+(?:COMP[_\s-]+)?(\d+)",
                r"EDITAL\s+N?[.º°]?\s*(\d+)",r"\bEd\s+Comp\s+(\d+)\b"]:
        for m in re.finditer(pat,sp,re.I):
            try: cands.append(int(m.group(1)))
            except ValueError: pass
    return min(cands) if cands else 9999

def parse_date(filename,head):
    sp=f"{filename}\n{head[:3000]}"
    m=re.search(r"\b(\d{1,2})[-_/](\d{1,2})[-_/](20\d{2}|19\d{2})\b",sp)
    if m: d,mo,y=m.groups(); return f"{y}-{int(mo):02d}-{int(d):02d}"
    m=re.search(r"\b(?:DE\s+)?(\d{1,2})\s+DE\s+([A-ZÇÃÉÊÍÓÔÕÚ]+)\s+DE\s+(20\d{2}|19\d{2})\b",sp,re.I)
    if m:
        d,mn,y=m.groups(); mo=MONTHS.get(strip_accents(mn.lower()))
        if mo: return f"{y}-{mo}-{int(d):02d}"
    return "9999-99-99"

def infer_stage(filename,head,doc_type):
    v=norm_key(f"{filename} {head[:3000]}")
    rules=[(0,"provisional_result",[r"RES PROV",r"RESULTADO PROVISORIO"]),
        (1,"objective_result",[r"RES FIN OBJ",r"PROVAS OBJETIVAS",r"PROVA OBJETIVA"]),
        (2,"discursive_or_practical_result",[r"DISC",r"DISCURSIVA",r"PROVA PRATICA",r"PRAT PROF"]),
        (3,"oral_physical_medical_result",[r"ORAL",r"CAP FIS",r"APTIDAO FISICA",r"PERICIA",r"EXAME MED"]),
        (4,"titles_or_training_result",[r"TIT",r"TITULOS",r"CURSO DE FORMACAO"]),
        (8,"final_concurso_result",[r"FIN CONC",r"RESULTADO FINAL NO CONCURSO",r"RESULTADO FINAL DO CONCURSO"]),
        (9,"homologation_or_approved_list",[r"HOMOLOG",r"LISTA DOS APROVADOS",r"RESULTADO FINAL EXAME APROVADO"])]
    for rank,label,pats in rules:
        if any(re.search(p,v) for p in pats): return rank,label
    if doc_type=="provisional_result": return 0,"provisional_result"
    if doc_type=="intermediate_result": return 2,"intermediate_result"
    if doc_type=="final_result": return 5,"generic_final_result"
    return 6,"other_candidate_result"

@dataclass
class Rank:
    text_id:str; concurso_id:str; filename:str; text_path:str; doc_type:str
    edital_number:int; doc_date:str; stage_rank:int; stage_label:str

def build_ranks(raw):
    docs={}
    for row in csv.DictReader(open(raw,encoding="utf-8")):
        docs.setdefault(row["text_id"],{"text_id":row["text_id"],"concurso_id":row["concurso_id"],
            "filename":row["filename"],"text_path":row["text_path"],"doc_type":row.get("doc_type","")})
    ranks={}
    for tid,d in docs.items():
        head=read_head(d["text_path"]); en=parse_edital(d["filename"],head); dt=parse_date(d["filename"],head)
        sr,sl=infer_stage(d["filename"],head,d["doc_type"])
        ranks[tid]=Rank(tid,d["concurso_id"],d["filename"],d["text_path"],d["doc_type"],en,dt,sr,sl)
    return ranks

def app_key(row,mode):
    nome=norm_key(row.get("nome") or "")
    if mode=="applicant": return sid([row["concurso_id"],row["inscricao"],nome])
    cargo=norm_key(row.get("cargo_raw") or "")
    return sid([row["concurso_id"],row["inscricao"],nome,norm_key(row.get("localidade") or ""),cargo])

def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw",default=str(DEFAULT_RAW)); ap.add_argument("--out-dir",default=str(DEFAULT_OUT))
    ap.add_argument("--key-mode",choices=["applicant","application"],default="applicant")
    args=ap.parse_args()
    ranks=build_ranks(args.raw)
    selected={}; sel_pri={}; dup={}
    reader=csv.DictReader(open(args.raw,encoding="utf-8")); raw_fields=reader.fieldnames or []
    for row in reader:
        k=app_key(row,args.key_mode); rk=ranks[row["text_id"]]
        pri=(rk.stage_rank,rk.edital_number,rk.doc_date,rk.filename,row["candidate_row_id"])
        dup[k]=dup.get(k,0)+1
        if k not in selected or pri<sel_pri[k]:
            o=dict(row); o["application_key"]=k; o["sel_stage_rank"]=str(rk.stage_rank)
            o["sel_stage_label"]=rk.stage_label; o["sel_edital_number"]=str(rk.edital_number)
            o["sel_doc_date"]=rk.doc_date; selected[k]=o; sel_pri[k]=pri
    for k,o in selected.items(): o["n_raw_rows_for_key"]=str(dup.get(k,1))
    rows=list(selected.values())
    rows.sort(key=lambda r:(r["year"],r["concurso_id"],r["inscricao"],norm_key(r["nome"])))
    extra=["application_key","sel_stage_rank","sel_stage_label","sel_edital_number","sel_doc_date","n_raw_rows_for_key"]
    suffix="earliest" if args.key_mode=="applicant" else "earliest_application"
    write_csv(Path(args.out_dir)/f"candidate_rows_all_{suffix}.csv",rows,extra+raw_fields)
    # summaries
    from collections import Counter
    bysel=Counter(r["selection_type"] for r in rows); bystage=Counter(r["sel_stage_label"] for r in rows)
    write_csv(Path(args.out_dir)/f"candidate_rows_all_{suffix}_selectiontype_counts.csv",
        [{"selection_type":k,"n_rows":v} for k,v in bysel.most_common()],["selection_type","n_rows"])
    write_csv(Path(args.out_dir)/f"candidate_rows_all_{suffix}_stage_counts.csv",
        [{"stage_label":k,"n_rows":v} for k,v in bystage.most_common()],["stage_label","n_rows"])
    print(f"raw rows read     : {sum(dup.values())}")
    print(f"earliest kept     : {len(rows)}")
    print(f"by selection_type : {dict(bysel)}")
    print(f"output            : {Path(args.out_dir)/f'candidate_rows_all_{suffix}.csv'}")

if __name__=="__main__": main()
