#!/usr/bin/env python3
"""
Build a first-pass CEBRASPE/CESPE PDF inventory and pilot applicant dataset.

This script is deliberately conservative. It uses pdftotext/pdfinfo plus simple,
auditable regexes before any LLM step. The goal is to identify high-value result
PDFs, extract text caches, and parse the common candidate-list layouts.

Example:
  python3 Data/CEBRASPE/Code/cebraspe_audit_pipeline.py \
    --year 2006 --concurso TRE_PA2006 --concurso TSE2006 --max-pdfs 200
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]  # <CEBRASPE> (parent of Code/)
RAW_ROOT = ROOT / "Raw Data" / "www.cespe.unb.br" / "concursos"
OUT_ROOT = ROOT / "Intermediate" / "audit_pipeline"


FILENAME_RULES = [
    ("answer_key", re.compile(r"\b(gab|gabarito|justificativas).*", re.I)),
    ("exam", re.compile(r"\b(prova|cargo_\d+|caderno)\b", re.I)),
    ("opening_notice", re.compile(r"\b(abt|abertura|edital_?1\b|ed_?1_).*", re.I)),
    ("demand", re.compile(r"\b(demanda|inscritos)\b", re.I)),
    ("final_result", re.compile(r"\b(res(?:ultado)?_?fin|resultado final|fin_?conc|homolog)\b", re.I)),
    ("provisional_result", re.compile(r"\b(res(?:ultado)?_?prov|provisorio|provis.rio)\b", re.I)),
    ("call_notice", re.compile(r"\b(conv|convoca|locais|horario|pericia|curso_de_formacao)\b", re.I)),
    ("erratum", re.compile(r"\b(ret|retif|errata|erro_material|sub_judice|judice)\b", re.I)),
    ("communication", re.compile(r"\b(comunicado|aviso|nota)\b", re.I)),
]

TEXT_RULES = [
    ("opening_notice", re.compile(r"torna p[úu]blica a realiza[çc][ãa]o de concurso|das inscri[çc][õo]es", re.I)),
    ("demand", re.compile(r"demanda de candidatos por vaga|inscritos\s+vagas\s+demanda", re.I)),
    ("final_result", re.compile(r"resultado final no concurso|resultado final\s*-|classifica[çc][ãa]o final", re.I)),
    ("provisional_result", re.compile(r"resultado provis[óo]rio|resultado prov", re.I)),
]


@dataclass
class PdfRecord:
    pdf_id: str
    path: str
    rel_path: str
    concurso: str
    year_dir: str
    filename: str
    size_bytes: int
    pages: int | None
    doc_type_filename: str
    doc_type_text: str
    doc_type: str
    text_chars: int
    candidate_like_hits: int


@dataclass
class CandidateRecord:
    pdf_id: str
    rel_path: str
    concurso: str
    document_name: str
    parser: str
    section: str
    inscricao: str
    nome: str
    nota_final: str
    classificacao: str
    cargo: str
    localidade: str


def norm_text_for_rules(value: str) -> str:
    return value.replace("_", " ").replace("-", " ")


def stable_id(path: Path) -> str:
    rel = str(path.relative_to(ROOT))
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]


def infer_year_and_concurso(path: Path) -> tuple[str, str]:
    parts = path.parts
    concurso = ""
    year_dir = ""
    if "concursos" in parts:
        i = parts.index("concursos")
        after = parts[i + 1 :]
        if after and after[0] == "_antigos" and len(after) >= 3:
            year_dir = after[1]
            concurso = after[2]
        elif after:
            concurso = after[0]
            m = re.search(r"(19|20)\d{2}", concurso)
            year_dir = m.group(0) if m else ""
    return year_dir, concurso


def classify_filename(filename: str) -> str:
    label = norm_text_for_rules(filename)
    for doc_type, pattern in FILENAME_RULES:
        if pattern.search(label):
            return doc_type
    return "other"


def classify_text(text: str) -> str:
    head = text[:5000]
    for doc_type, pattern in TEXT_RULES:
        if pattern.search(head):
            return doc_type
    return "unknown"


def choose_doc_type(filename_type: str, text_type: str) -> str:
    if text_type != "unknown":
        return text_type
    return filename_type


def run_text_extract(pdf: Path, first_pages: int) -> str:
    cmd = ["pdftotext", "-layout", "-f", "1", "-l", str(first_pages), str(pdf), "-"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def pdf_pages(pdf: Path) -> int | None:
    if not shutil.which("pdfinfo"):
        return None
    result = subprocess.run(["pdfinfo", str(pdf)], text=True, capture_output=True)
    if result.returncode != 0:
        return None
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, flags=re.M)
    return int(match.group(1)) if match else None


def iter_pdfs(year: str | None, concursos: set[str], max_pdfs: int | None) -> Iterable[Path]:
    count = 0
    for pdf in sorted(RAW_ROOT.rglob("*")):
        if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
            continue
        year_dir, concurso = infer_year_and_concurso(pdf)
        if year and year_dir != year:
            continue
        if concursos and concurso not in concursos:
            continue
        yield pdf
        count += 1
        if max_pdfs is not None and count >= max_pdfs:
            return


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def candidate_hit_count(text: str) -> int:
    return len(re.findall(r"\b\d{6,8}\b", text))


def parse_prose_candidate_lists(text: str, rec: PdfRecord) -> list[CandidateRecord]:
    rows: list[CandidateRecord] = []
    section_re = re.compile(r"^(?P<num>\d+(?:\.\d+)+)\s+(?P<title>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9 :/–\-,()]+)$")
    item_re = re.compile(
        r"(?P<insc>\d{6,8}),\s*(?P<nome>[^,/]+?),\s*(?P<nota>\d+[,.]\d+),\s*(?P<class>\d+)(?=\s*/|\.|\s*$)"
    )

    current_section = ""
    buffer = ""
    for raw_line in text.splitlines() + ["1. END"]:
        line = raw_line.strip()
        section_match = section_re.match(line)
        if section_match:
            if current_section and buffer:
                rows.extend(records_from_prose_buffer(buffer, rec, current_section, item_re))
            current_section = section_match.group("title").strip()
            buffer = ""
        elif current_section:
            buffer += " " + line
    return rows


def records_from_prose_buffer(
    buffer: str, rec: PdfRecord, section: str, item_re: re.Pattern[str]
) -> list[CandidateRecord]:
    rows = []
    for match in item_re.finditer(buffer):
        rows.append(
            CandidateRecord(
                pdf_id=rec.pdf_id,
                rel_path=rec.rel_path,
                concurso=rec.concurso,
                document_name=rec.filename,
                parser="prose_slash_list",
                section=section,
                inscricao=match.group("insc"),
                nome=match.group("nome").strip(),
                nota_final=match.group("nota").replace(",", "."),
                classificacao=match.group("class"),
                cargo=section,
                localidade="",
            )
        )
    return rows


def parse_fixed_width_result_table(text: str, rec: PdfRecord) -> list[CandidateRecord]:
    rows: list[CandidateRecord] = []
    row_re = re.compile(r"^(?P<insc>\d{6,8})\s+(?P<name>.+?)\s+(?P<score>\d+[,.]\d+)\s+(?P<class>\d+)\s+(?P<cargo>.+)$")
    locality = ""
    for line in text.splitlines():
        stripped = line.strip()
        loc_match = re.match(r"^(TRE|TSE)\s*/\s*([A-Z]{2})$", stripped)
        if loc_match:
            locality = stripped
            continue
        match = row_re.match(stripped)
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group("name")).strip()
        cargo = re.sub(r"\s+", " ", match.group("cargo")).strip()
        if len(name.split()) < 2 or "Inscrição" in name:
            continue
        rows.append(
            CandidateRecord(
                pdf_id=rec.pdf_id,
                rel_path=rec.rel_path,
                concurso=rec.concurso,
                document_name=rec.filename,
                parser="fixed_width_result_table",
                section="",
                inscricao=match.group("insc"),
                nome=name,
                nota_final=match.group("score").replace(",", "."),
                classificacao=match.group("class"),
                cargo=cargo,
                localidade=locality,
            )
        )
    return rows


def parse_candidates(text: str, rec: PdfRecord) -> list[CandidateRecord]:
    rows = parse_fixed_width_result_table(text, rec)
    rows.extend(parse_prose_candidate_lists(text, rec))
    seen = set()
    unique = []
    for row in rows:
        key = (row.pdf_id, row.inscricao, row.nome, row.nota_final, row.classificacao, row.cargo)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def build_outputs(args: argparse.Namespace) -> None:
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext not found. Install poppler before running this script.")

    out_dir = Path(args.output_dir)
    text_dir = out_dir / "text_cache"
    text_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[PdfRecord] = []
    candidate_rows: list[CandidateRecord] = []

    for pdf in iter_pdfs(args.year, set(args.concurso), args.max_pdfs):
        pdf_id = stable_id(pdf)
        rel_path = str(pdf.relative_to(ROOT))
        year_dir, concurso = infer_year_and_concurso(pdf)
        text = run_text_extract(pdf, args.first_pages)
        text_path = text_dir / f"{pdf_id}.txt"
        text_path.write_text(text, encoding="utf-8")

        filename_type = classify_filename(pdf.name)
        text_type = classify_text(text)
        rec = PdfRecord(
            pdf_id=pdf_id,
            path=str(pdf),
            rel_path=rel_path,
            concurso=concurso,
            year_dir=year_dir,
            filename=pdf.name,
            size_bytes=pdf.stat().st_size,
            pages=pdf_pages(pdf),
            doc_type_filename=filename_type,
            doc_type_text=text_type,
            doc_type=choose_doc_type(filename_type, text_type),
            text_chars=len(text),
            candidate_like_hits=candidate_hit_count(text),
        )
        manifest.append(rec)

        if rec.doc_type in {"final_result", "provisional_result"} and rec.candidate_like_hits:
            candidate_rows.extend(parse_candidates(text, rec))

    write_csv(out_dir / "pdf_manifest.csv", [asdict(r) for r in manifest], list(asdict(manifest[0]).keys()) if manifest else [])
    write_csv(
        out_dir / "candidate_rows_pilot.csv",
        [asdict(r) for r in candidate_rows],
        list(asdict(candidate_rows[0]).keys()) if candidate_rows else [f.name for f in CandidateRecord.__dataclass_fields__.values()],
    )

    counts: dict[str, int] = {}
    for rec in manifest:
        counts[rec.doc_type] = counts.get(rec.doc_type, 0) + 1
    summary_rows = [{"doc_type": k, "n_pdfs": v} for k, v in sorted(counts.items())]
    write_csv(out_dir / "doc_type_counts.csv", summary_rows, ["doc_type", "n_pdfs"])

    print(f"PDFs inventoried: {len(manifest)}")
    print(f"Candidate rows parsed by pilot rules: {len(candidate_rows)}")
    print(f"Output directory: {out_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", help="Restrict to a year directory, e.g. 2006.")
    parser.add_argument("--concurso", action="append", default=[], help="Restrict to concurso folder. Repeatable.")
    parser.add_argument("--max-pdfs", type=int, help="Stop after N PDFs.")
    parser.add_argument("--first-pages", type=int, default=9999, help="Pages to extract per PDF.")
    parser.add_argument("--output-dir", default=str(OUT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    build_outputs(parse_args())
