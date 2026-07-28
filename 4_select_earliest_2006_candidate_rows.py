#!/usr/bin/env python3
"""
Collapse raw 2006 candidate rows to the earliest/preliminary result per applicant.

The raw extraction intentionally keeps many rows for the same applicant across
provisional, final, title, medical, and homologation documents. This script keeps
one row per applicant/application key using a transparent document priority:

1. More preliminary result-stage language first.
2. Lower edital/complement number first.
3. Earlier document date first, when recoverable.
4. Smaller source filename as deterministic tie-breaker.

The output keeps the selected source row plus ranking diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_ROWS = ROOT / "Data" / "CEBRASPE" / "Intermediate" / "candidate_extraction_2006" / "candidate_rows_2006_raw.csv"
DEFAULT_OUT_DIR = ROOT / "Data" / "CEBRASPE" / "Intermediate" / "candidate_extraction_2006"


MONTHS = {
    "janeiro": "01",
    "fevereiro": "02",
    "marco": "03",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


@dataclass
class DocumentRank:
    text_id: str
    concurso_id: str
    filename: str
    text_path: str
    doc_type_rule: str
    edital_number: int
    doc_date: str
    stage_rank: int
    stage_label: str
    doc_priority_tuple: str


def strip_accents(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def norm_key(value: str) -> str:
    value = strip_accents(value or "").upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def stable_id(parts: list[str]) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:20]


def read_head(path: str, chars: int = 8000) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:chars]
    except OSError:
        return ""


def parse_edital_number(filename: str, text_head: str) -> int:
    candidates: list[int] = []
    search_space = f"{filename}\n{text_head[:2500]}"
    patterns = [
        r"EDITAL\s+COMPLEMENTAR\s+N?[.º°]?\s*(\d+)",
        r"ED(?:ITAL)?[_\s-]+(?:COMP[_\s-]+)?(\d+)",
        r"EDITAL\s+N?[.º°]?\s*(\d+)",
        r"\bEd\s+Comp\s+(\d+)\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, search_space, flags=re.I):
            try:
                candidates.append(int(match.group(1)))
            except ValueError:
                pass
    return min(candidates) if candidates else 9999


def parse_doc_date(filename: str, text_head: str) -> str:
    search_space = f"{filename}\n{text_head[:3000]}"
    numeric = re.search(r"\b(\d{1,2})[-_/](\d{1,2})[-_/](20\d{2}|19\d{2})\b", search_space)
    if numeric:
        day, month, year = numeric.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    word = re.search(
        r"\b(?:DE\s+)?(\d{1,2})\s+DE\s+([A-ZÇÃÉÊÍÓÔÕÚ]+)\s+DE\s+(20\d{2}|19\d{2})\b",
        search_space,
        flags=re.I,
    )
    if word:
        day, month_name, year = word.groups()
        month = MONTHS.get(strip_accents(month_name.lower()), MONTHS.get(month_name.lower()))
        if month:
            return f"{year}-{month}-{int(day):02d}"
    return "9999-99-99"


def infer_stage(filename: str, text_head: str, doc_type_rule: str) -> tuple[int, str]:
    value = norm_key(f"{filename} {text_head[:3000]}")

    # Broad rule: keep earliest/preliminary result, not final homologation.
    rules = [
        (0, "provisional_result", [r"RES PROV", r"RESULTADO PROVISORIO"]),
        (1, "objective_result", [r"RES FIN OBJ", r"PROVAS OBJETIVAS", r"PROVA OBJETIVA"]),
        (2, "discursive_or_practical_result", [r"DISC", r"DISCURSIVA", r"PROVA PRATICA", r"PRAT PROF"]),
        (3, "oral_physical_medical_result", [r"ORAL", r"CAP FIS", r"APTIDAO FISICA", r"PERICIA", r"EXAME MED"]),
        (4, "titles_or_training_result", [r"TIT", r"TITULOS", r"CURSO DE FORMACAO"]),
        (8, "final_concurso_result", [r"FIN CONC", r"RESULTADO FINAL NO CONCURSO", r"RESULTADO FINAL DO CONCURSO"]),
        (9, "homologation_or_approved_list", [r"HOMOLOG", r"LISTA DOS APROVADOS", r"RESULTADO FINAL EXAME APROVADO"]),
    ]
    for rank, label, patterns in rules:
        if any(re.search(pattern, value) for pattern in patterns):
            return rank, label
    if doc_type_rule == "provisional_result":
        return 0, "provisional_result"
    if doc_type_rule == "intermediate_result":
        return 2, "intermediate_result"
    if doc_type_rule == "final_result":
        return 5, "generic_final_result"
    return 6, "other_candidate_result"


def build_document_ranks(rows_path: Path) -> dict[str, DocumentRank]:
    docs: dict[str, dict[str, str]] = {}
    with rows_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            docs.setdefault(
                row["text_id"],
                {
                    "text_id": row["text_id"],
                    "concurso_id": row["concurso_id"],
                    "filename": row["filename"],
                    "text_path": row["text_path"],
                    "doc_type_rule": row["doc_type_rule"],
                },
            )

    ranks: dict[str, DocumentRank] = {}
    for text_id, doc in docs.items():
        head = read_head(doc["text_path"])
        edital_number = parse_edital_number(doc["filename"], head)
        doc_date = parse_doc_date(doc["filename"], head)
        stage_rank, stage_label = infer_stage(doc["filename"], head, doc["doc_type_rule"])
        priority = (stage_rank, edital_number, doc_date, doc["filename"])
        ranks[text_id] = DocumentRank(
            text_id=text_id,
            concurso_id=doc["concurso_id"],
            filename=doc["filename"],
            text_path=doc["text_path"],
            doc_type_rule=doc["doc_type_rule"],
            edital_number=edital_number,
            doc_date=doc_date,
            stage_rank=stage_rank,
            stage_label=stage_label,
            doc_priority_tuple=str(priority),
        )
    return ranks


def row_application_key(row: dict[str, str], key_mode: str) -> str:
    nome = norm_key(row.get("nome") or "")
    if key_mode == "applicant":
        return stable_id([row["concurso_id"], row["inscricao"], nome])

    # More granular mode: keep cargo/localidade in the key so multi-cargo
    # concursos do not collapse accidentally. When cargo is missing, fall back
    # to section title.
    cargo = norm_key(row.get("cargo_raw") or row.get("section_title") or "")
    localidade = norm_key(row.get("localidade") or "")
    parts = [row["concurso_id"], row["inscricao"], nome, localidade, cargo]
    return stable_id(parts)


def doc_priority(rank: DocumentRank) -> tuple[int, int, str, str]:
    return (rank.stage_rank, rank.edital_number, rank.doc_date, rank.filename)


def row_priority(row: dict[str, str], rank: DocumentRank) -> tuple[int, int, str, str, str]:
    return (*doc_priority(rank), row["candidate_row_id"])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-rows", default=str(DEFAULT_RAW_ROWS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--key-mode",
        choices=["applicant", "application"],
        default="applicant",
        help="applicant keeps one row per concurso/inscricao/name; application also separates cargo/localidade.",
    )
    args = parser.parse_args()

    raw_path = Path(args.raw_rows)
    out_dir = Path(args.out_dir)
    ranks = build_document_ranks(raw_path)

    selected: dict[str, dict[str, str]] = {}
    selected_priority: dict[str, tuple[int, int, str, str, str]] = {}
    duplicate_counts: dict[str, int] = {}

    with raw_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        raw_fields = reader.fieldnames or []
        for row in reader:
            app_key = row_application_key(row, args.key_mode)
            rank = ranks[row["text_id"]]
            priority = row_priority(row, rank)
            duplicate_counts[app_key] = duplicate_counts.get(app_key, 0) + 1
            if app_key not in selected or priority < selected_priority[app_key]:
                out = dict(row)
                out["application_key"] = app_key
                out["selected_doc_stage_rank"] = str(rank.stage_rank)
                out["selected_doc_stage_label"] = rank.stage_label
                out["selected_doc_edital_number"] = str(rank.edital_number)
                out["selected_doc_date"] = rank.doc_date
                out["selected_doc_priority_tuple"] = rank.doc_priority_tuple
                selected[app_key] = out
                selected_priority[app_key] = priority

    for app_key, row in selected.items():
        row["n_raw_rows_for_application_key"] = str(duplicate_counts.get(app_key, 1))

    selected_rows = list(selected.values())
    selected_rows.sort(key=lambda r: (r["concurso_id"], r["inscricao"], norm_key(r["nome"]), norm_key(r["cargo_raw"])))

    extra_fields = [
        "application_key",
        "selected_doc_stage_rank",
        "selected_doc_stage_label",
        "selected_doc_edital_number",
        "selected_doc_date",
        "selected_doc_priority_tuple",
        "n_raw_rows_for_application_key",
    ]
    suffix = "earliest" if args.key_mode == "applicant" else "earliest_application"
    write_csv(out_dir / f"candidate_rows_2006_{suffix}.csv", selected_rows, extra_fields + raw_fields)
    write_csv(out_dir / "candidate_extraction_2006_document_ranks.csv", [asdict(r) for r in ranks.values()], list(DocumentRank.__dataclass_fields__.keys()))

    by_stage: dict[str, int] = {}
    by_concurso: dict[str, int] = {}
    for row in selected_rows:
        by_stage[row["selected_doc_stage_label"]] = by_stage.get(row["selected_doc_stage_label"], 0) + 1
        by_concurso[row["concurso_id"]] = by_concurso.get(row["concurso_id"], 0) + 1
    write_csv(
        out_dir / f"candidate_rows_2006_{suffix}_stage_counts.csv",
        [{"stage_label": k, "n_rows": v} for k, v in sorted(by_stage.items())],
        ["stage_label", "n_rows"],
    )
    write_csv(
        out_dir / f"candidate_rows_2006_{suffix}_concurso_counts.csv",
        [{"concurso_id": k, "n_rows": v} for k, v in sorted(by_concurso.items())],
        ["concurso_id", "n_rows"],
    )

    print(f"Raw rows read: {sum(duplicate_counts.values())}")
    print(f"Earliest rows kept: {len(selected_rows)}")
    print(f"Application keys with duplicates: {sum(1 for v in duplicate_counts.values() if v > 1)}")
    print(f"Key mode: {args.key_mode}")
    print(f"Output: {out_dir / f'candidate_rows_2006_{suffix}.csv'}")


if __name__ == "__main__":
    main()
