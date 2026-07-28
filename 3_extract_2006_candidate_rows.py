#!/usr/bin/env python3
"""
First-pass extraction of candidate-level rows from 2006 CEBRASPE result texts.

This reads the document classification queue created by `2_classify_2006_texts.py`
and writes raw candidate rows with provenance. It is not the final analytical
dataset: it is a high-recall extraction layer for parser QA and deduplication.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUEUE = ROOT / "Data" / "CEBRASPE" / "Intermediate" / "classification_2006" / "classification_2006_result_extraction_queue.csv"
DEFAULT_OUT_DIR = ROOT / "Data" / "CEBRASPE" / "Intermediate" / "candidate_extraction_2006"


HEADING_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)(?:\.\s*)?\s+(?P<title>\S.{1,220}?)\s*$")
INSCRICAO_RE = re.compile(r"\b\d{6,8}\b")
NUMERIC_RE = re.compile(r"^\d{1,6}(?:[,.]\d{1,4})?$")

# Slash/prose examples:
# 00001571, Alex Bonente Melo, 7.13, 13 /
# 00002056, Adriani Medeiros Flores, 64.00, 6.75 /
PROSE_WITH_NUMBERS_RE = re.compile(
    r"(?P<inscricao>\b\d{6,8}\b),\s*"
    r"(?P<nome>[^,/]{3,160}?)\s*,\s*"
    r"(?P<numbers>\d{1,6}(?:[,.]\d{1,4})?(?:\s*,\s*\d{1,6}(?:[,.]\d{1,4})?){0,5})"
    r"(?=\s*/|\s*\.(?:\s|$)|\s*$)"
)

# Status-only examples:
# 00001140, Alexandre Calvinho Broni / 00000407, Beatriz ...
PROSE_NO_SCORE_RE = re.compile(
    r"(?P<inscricao>\b\d{6,8}\b),\s*(?P<nome>[^,/]{3,160}?)(?=\s*/|\s*\.(?:\s|$)|\s*$)"
)

# Fixed-width examples:
# 00180265 ADRIANO SALES SANTOS 7.68 13 Técnico Judiciário ...
FIXED_WIDTH_RE = re.compile(
    r"^(?P<inscricao>\d{6,8})\s+"
    r"(?P<nome>.+?)\s+"
    r"(?P<nota>\d{1,4}[,.]\d{1,4})\s+"
    r"(?P<classificacao>\d{1,6})\s+"
    r"(?P<cargo>.+?)\s*$"
)

LOCATION_HEADING_RE = re.compile(r"^(?:TRE|TSE|TRT|TRF|TJ|MP|PC|PM|SEAD|SEDUC|SES|SEE)\s*/?\s*[A-Z]{0,3}$|^TRE/[A-Z]{2}$")
LEVEL_HEADING_RE = re.compile(r"N[ÍI]VEL\s+(?:SUPERIOR|M[ÉE]DIO|FUNDAMENTAL)", flags=re.I)
RESULT_HEADING_RE = re.compile(r"resultado|rela..o|convoca|disposi..es|recurso|per.cia|inscri..o", flags=re.I)


@dataclass
class CandidateRow:
    candidate_row_id: str
    text_id: str
    year_dir: str
    concurso_id: str
    doc_type_rule: str
    text_path: str
    original_pdf_path: str
    filename: str
    parser: str
    section_number: str
    section_title: str
    nivel: str
    localidade: str
    cargo_raw: str
    inscricao: str
    nome: str
    numeric_values_raw: str
    nota_1: str
    nota_2: str
    nota_3: str
    classificacao: str
    status_raw: str
    is_sub_judice_context: int
    source_context: str


@dataclass
class DocumentSummary:
    text_id: str
    year_dir: str
    concurso_id: str
    doc_type_rule: str
    filename: str
    text_path: str
    original_pdf_path: str
    n_registration_like: int
    n_score_rank_like: int
    n_rows_extracted: int
    n_rows_prose_numbers: int
    n_rows_prose_no_score: int
    n_rows_fixed_width: int
    extraction_coverage_vs_registration_like: float
    needs_parser_review: int


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def upper_ratio(value: str) -> float:
    letters = [ch for ch in value if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(ch.isupper() for ch in letters) / len(letters)


def is_context_heading(title: str) -> bool:
    title = compact(title)
    if len(title) < 3:
        return False
    if LOCATION_HEADING_RE.search(title):
        return True
    if LEVEL_HEADING_RE.search(title):
        return True
    if upper_ratio(title) >= 0.65 and not RESULT_HEADING_RE.search(title):
        return True
    if re.search(r"\b(CARGO|ANALISTA|T[ÉE]CNICO|PROFESSOR|DELEGADO|INVESTIGADOR|ESCRIV|PERITO|JUIZ|PROMOTOR|ADVOGADO|AUDITOR)\b", title, flags=re.I):
        return not RESULT_HEADING_RE.search(title)
    return False


def split_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current_lines: list[str] = []
    current_num = ""
    current_title = ""
    current_level = ""
    current_location = ""
    current_cargo = ""

    def flush() -> None:
        nonlocal current_lines
        block_text = compact(" ".join(current_lines))
        if block_text:
            blocks.append(
                {
                    "section_number": current_num,
                    "section_title": current_title,
                    "nivel": current_level,
                    "localidade": current_location,
                    "cargo_raw": current_cargo,
                    "text": block_text,
                }
            )
        current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        match = HEADING_RE.match(stripped)
        if match:
            title = compact(match.group("title"))
            if is_context_heading(title) or RESULT_HEADING_RE.search(title):
                flush()
                current_num = match.group("num")
                current_title = title
                if LOCATION_HEADING_RE.search(title):
                    current_location = title
                elif LEVEL_HEADING_RE.search(title):
                    current_level = title
                elif is_context_heading(title):
                    current_cargo = title
                continue
        current_lines.append(stripped)
    flush()
    return blocks


def numbers_to_fields(numbers_raw: str, context: str) -> tuple[str, str, str, str]:
    values = [n.strip().replace(",", ".") for n in numbers_raw.split(",") if n.strip()]
    nota_1 = values[0] if len(values) >= 1 else ""
    nota_2 = values[1] if len(values) >= 2 else ""
    nota_3 = values[2] if len(values) >= 3 else ""
    classificacao = ""

    context_l = context.lower()
    if values:
        last = values[-1]
        last_is_integer = re.fullmatch(r"\d{1,6}", last or "") is not None
        mentions_classification = "classifica" in context_l or "classificação" in context_l
        if last_is_integer and (mentions_classification or len(values) == 2):
            classificacao = last
            if len(values) == 2:
                nota_2 = ""
            elif len(values) == 3:
                nota_3 = ""
    return nota_1, nota_2, nota_3, classificacao


def normalize_numbers_raw(numbers_raw: str) -> str:
    values = [n.strip().replace(",", ".") for n in numbers_raw.split(",") if n.strip()]
    return "; ".join(values)


def make_id(parts: list[str]) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:20]


def row_from_match(
    queue_row: dict[str, str],
    parser: str,
    block: dict[str, str],
    inscricao: str,
    nome: str,
    numeric_values_raw: str,
    status_raw: str,
    cargo_override: str = "",
) -> CandidateRow:
    context = " | ".join(
        part
        for part in [block.get("section_title", ""), block.get("cargo_raw", ""), block.get("text", "")[:300]]
        if part
    )
    nota_1, nota_2, nota_3, classificacao = numbers_to_fields(numeric_values_raw, context)
    cargo_raw = cargo_override or block.get("cargo_raw", "")
    row_id = make_id(
        [
            queue_row["text_id"],
            parser,
            block.get("section_number", ""),
            cargo_raw,
            inscricao,
            compact(nome),
            numeric_values_raw,
            status_raw,
        ]
    )
    return CandidateRow(
        candidate_row_id=row_id,
        text_id=queue_row["text_id"],
        year_dir=queue_row["year_dir"],
        concurso_id=queue_row["concurso_id"],
        doc_type_rule=queue_row["doc_type_rule"],
        text_path=queue_row["text_path"],
        original_pdf_path=queue_row["original_pdf_path"],
        filename=queue_row["filename"],
        parser=parser,
        section_number=block.get("section_number", ""),
        section_title=block.get("section_title", ""),
        nivel=block.get("nivel", ""),
        localidade=block.get("localidade", ""),
        cargo_raw=cargo_raw,
        inscricao=inscricao,
        nome=compact(nome).strip(" ,.;"),
        numeric_values_raw=normalize_numbers_raw(numeric_values_raw),
        nota_1=nota_1,
        nota_2=nota_2,
        nota_3=nota_3,
        classificacao=classificacao,
        status_raw=status_raw,
        is_sub_judice_context=int(bool(re.search(r"sub\s+judice|liminar|decis.o\s+judicial", context, flags=re.I))),
        source_context=compact(context[:700]),
    )


def parse_prose_blocks(text: str, queue_row: dict[str, str]) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for block in split_blocks(text):
        block_text = block["text"]
        occupied_spans: list[tuple[int, int]] = []
        for match in PROSE_WITH_NUMBERS_RE.finditer(block_text):
            nome = match.group("nome")
            if not plausible_name(nome):
                continue
            occupied_spans.append(match.span())
            rows.append(
                row_from_match(
                    queue_row=queue_row,
                    parser="prose_slash_numbers",
                    block=block,
                    inscricao=match.group("inscricao"),
                    nome=nome,
                    numeric_values_raw=match.group("numbers"),
                    status_raw="",
                )
            )

        # Pull status-only rows only in blocks that do not look like score lists.
        if occupied_spans:
            continue
        for match in PROSE_NO_SCORE_RE.finditer(block_text):
            nome = match.group("nome")
            if not plausible_name(nome):
                continue
            rows.append(
                row_from_match(
                    queue_row=queue_row,
                    parser="prose_slash_no_score",
                    block=block,
                    inscricao=match.group("inscricao"),
                    nome=nome,
                    numeric_values_raw="",
                    status_raw=infer_status(block),
                )
            )
    return rows


def plausible_name(value: str) -> bool:
    value = compact(value)
    if len(value) < 5 or len(value) > 160:
        return False
    if NUMERIC_RE.fullmatch(value):
        return False
    if re.search(r"\b(Edital|Resultado|Cargo|Nível|Página|CESPE|UnB|Concurso|Data de cria)\b", value, flags=re.I):
        return False
    return len(value.split()) >= 2


def infer_status(block: dict[str, str]) -> str:
    context = " ".join([block.get("section_title", ""), block.get("text", "")[:250]])
    status_phrases = [
        "resultado final na investigação social",
        "resultado provisório",
        "resultado final",
        "convocação",
        "eliminado",
        "deferido",
        "indeferido",
        "apto",
        "inapto",
    ]
    low = context.lower()
    for phrase in status_phrases:
        if phrase in low:
            return phrase
    return ""


def parse_fixed_width(text: str, queue_row: dict[str, str]) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    block = {
        "section_number": "",
        "section_title": "fixed-width table",
        "nivel": "",
        "localidade": "",
        "cargo_raw": "",
        "text": "",
    }
    for line in text.splitlines():
        stripped = compact(line)
        if not stripped:
            continue
        if LOCATION_HEADING_RE.match(stripped):
            block["localidade"] = stripped
            continue
        match = FIXED_WIDTH_RE.match(stripped)
        if not match:
            continue
        nome = match.group("nome")
        cargo = match.group("cargo")
        if not plausible_name(nome) or re.search(r"Inscri..o|Nome|Classifica", nome, flags=re.I):
            continue
        rows.append(
            row_from_match(
                queue_row=queue_row,
                parser="fixed_width_table",
                block=block,
                inscricao=match.group("inscricao"),
                nome=nome,
                numeric_values_raw=f"{match.group('nota')}, {match.group('classificacao')}",
                status_raw="",
                cargo_override=cargo,
            )
        )
    return rows


def dedupe_rows(rows: list[CandidateRow]) -> list[CandidateRow]:
    by_id: dict[str, CandidateRow] = {}
    for row in rows:
        by_id.setdefault(row.candidate_row_id, row)
    return list(by_id.values())


def extract_document(queue_row: dict[str, str]) -> tuple[list[CandidateRow], DocumentSummary]:
    path = Path(queue_row["text_path"])
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = parse_fixed_width(text, queue_row)
    rows.extend(parse_prose_blocks(text, queue_row))
    rows = dedupe_rows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.parser] = counts.get(row.parser, 0) + 1
    n_reg = int(queue_row.get("n_registration_like") or len(INSCRICAO_RE.findall(text)))
    coverage = round(len(rows) / n_reg, 4) if n_reg else 0.0
    summary = DocumentSummary(
        text_id=queue_row["text_id"],
        year_dir=queue_row["year_dir"],
        concurso_id=queue_row["concurso_id"],
        doc_type_rule=queue_row["doc_type_rule"],
        filename=queue_row["filename"],
        text_path=queue_row["text_path"],
        original_pdf_path=queue_row["original_pdf_path"],
        n_registration_like=n_reg,
        n_score_rank_like=int(queue_row.get("n_score_rank_like") or 0),
        n_rows_extracted=len(rows),
        n_rows_prose_numbers=counts.get("prose_slash_numbers", 0),
        n_rows_prose_no_score=counts.get("prose_slash_no_score", 0),
        n_rows_fixed_width=counts.get("fixed_width_table", 0),
        extraction_coverage_vs_registration_like=coverage,
        needs_parser_review=int((n_reg >= 20 and len(rows) == 0) or (n_reg >= 100 and coverage < 0.25)),
    )
    return rows, summary


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, help="Only process the first N queue rows.")
    parser.add_argument("--doc-type", action="append", help="Restrict to a doc_type_rule. Repeatable.")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    out_dir = Path(args.out_dir)
    queue_rows = list(csv.DictReader(queue_path.open(encoding="utf-8")))
    if args.doc_type:
        allowed = set(args.doc_type)
        queue_rows = [row for row in queue_rows if row["doc_type_rule"] in allowed]
    if args.limit:
        queue_rows = queue_rows[: args.limit]

    all_rows: list[CandidateRow] = []
    summaries: list[DocumentSummary] = []
    for queue_row in queue_rows:
        rows, summary = extract_document(queue_row)
        all_rows.extend(rows)
        summaries.append(summary)

    row_fields = list(CandidateRow.__dataclass_fields__.keys())
    summary_fields = list(DocumentSummary.__dataclass_fields__.keys())
    write_csv(out_dir / "candidate_rows_2006_raw.csv", [asdict(row) for row in all_rows], row_fields)
    write_csv(out_dir / "candidate_extraction_2006_document_summary.csv", [asdict(row) for row in summaries], summary_fields)
    review_rows = [asdict(row) for row in summaries if row.needs_parser_review]
    review_rows.sort(key=lambda row: (-int(row["n_registration_like"]), row["concurso_id"], row["filename"]))
    write_csv(out_dir / "candidate_extraction_2006_parser_review_queue.csv", review_rows, summary_fields)

    parser_counts: dict[str, int] = {}
    for row in all_rows:
        parser_counts[row.parser] = parser_counts.get(row.parser, 0) + 1
    write_csv(
        out_dir / "candidate_extraction_2006_parser_counts.csv",
        [{"parser": k, "n_rows": v} for k, v in sorted(parser_counts.items())],
        ["parser", "n_rows"],
    )

    print(f"Documents processed: {len(queue_rows)}")
    print(f"Candidate rows extracted: {len(all_rows)}")
    print(f"Documents needing parser review: {sum(s.needs_parser_review for s in summaries)}")
    print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
