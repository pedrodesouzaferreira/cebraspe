#!/usr/bin/env python3
"""
Classify the 2006 CEBRASPE/CESPE text corpus into document types.

Inputs are the pdftotext outputs in:
  Data/CEBRASPE/Raw Data/text/2006

Outputs are editable CSVs in:
  Data/CEBRASPE/Intermediate/classification_2006

The key output is `classification_2006_editable.csv`. Edit `manual_doc_type`,
`manual_notes`, or `exclude_from_llm` there, then use the `needs_llm_review`
column to choose documents for a later LLM classification pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEXT_DIR = ROOT / "Data" / "CEBRASPE" / "Raw Data" / "text" / "2006"
DEFAULT_OUT_DIR = ROOT / "Data" / "CEBRASPE" / "Intermediate" / "classification_2006"


DOC_TYPES = [
    "opening_notice",
    "final_result",
    "provisional_result",
    "intermediate_result",
    "convocation",
    "locations",
    "demand",
    "answer_key",
    "exam",
    "erratum",
    "appeals",
    "communication",
    "manual_or_regulation",
    "administrative",
    "other",
]


@dataclass
class Rule:
    doc_type: str
    pattern: re.Pattern[str]
    weight: int
    field: str
    evidence: str


@dataclass
class ClassifiedText:
    text_id: str
    text_path: str
    filename: str
    source_pdf_guess: str
    concurso_guess: str
    doc_type_rule: str
    confidence: float
    needs_llm_review: int
    score_opening_notice: int
    score_final_result: int
    score_provisional_result: int
    score_intermediate_result: int
    score_convocation: int
    score_locations: int
    score_demand: int
    score_answer_key: int
    score_exam: int
    score_erratum: int
    score_appeals: int
    score_communication: int
    score_manual_or_regulation: int
    score_administrative: int
    score_other: int
    evidence: str
    text_chars: int
    n_pages_markers: int
    n_registration_like: int
    n_score_rank_like: int
    has_candidate_table_header: int
    has_result_phrase: int
    head_snippet: str
    candidate_snippet: str
    manual_doc_type: str
    manual_notes: str
    exclude_from_llm: str


def rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, flags=re.I | re.M)


FILENAME_RULES = [
    Rule("answer_key", rx(r"(^|[^A-Z0-9])(gab|gabarito|gabaritos|justificativas?\s+de\s+alteracao\s+de\s+gabarito)([^A-Z0-9]|$)"), 12, "filename", "filename answer-key token"),
    Rule("exam", rx(r"(^|[^A-Z0-9])(prova|caderno|cargo\s?\d+|caderno\s?\w+)([^A-Z0-9]|$)"), 8, "filename", "filename exam token"),
    Rule("demand", rx(r"(^|[^A-Z0-9])(demanda|quantitativos?\s+inscritos|inscritos)([^A-Z0-9]|$)"), 12, "filename", "filename demand token"),
    Rule("opening_notice", rx(r"(^|[^A-Z0-9])(abt|abertura|ed\s?1\s.*|edital\s?1\s.*)([^A-Z0-9]|$)"), 7, "filename", "filename opening token"),
    Rule("final_result", rx(r"(^|[^A-Z0-9])(res\s?fin|resultado\s?final|fin\s?conc|homolog|homologacao)([^A-Z0-9]|$)"), 9, "filename", "filename final-result token"),
    Rule("provisional_result", rx(r"(^|[^A-Z0-9])(res\s?prov|resultado\s?provis|provisorio|provis.rio)([^A-Z0-9]|$)"), 8, "filename", "filename provisional-result token"),
    Rule("convocation", rx(r"(^|[^A-Z0-9])(conv|convoc|convocacao|convoca..o|curso\s?de\s?formacao|matricula|nomea)([^A-Z0-9]|$)"), 7, "filename", "filename convocation token"),
    Rule("locations", rx(r"(^|[^A-Z0-9])(locais?|horario|local\s?e\s?horario)([^A-Z0-9]|$)"), 8, "filename", "filename location token"),
    Rule("erratum", rx(r"(^|[^A-Z0-9])(ret|retif|retificacao|errata|erro\s?material|sub\s?judice|judice|liminar)([^A-Z0-9]|$)"), 7, "filename", "filename erratum/sub-judice token"),
    Rule("appeals", rx(r"(^|[^A-Z0-9])(recurso|recursos|anulacao|alteracao\s?de\s?gabarito|razoes)([^A-Z0-9]|$)"), 7, "filename", "filename appeals token"),
    Rule("communication", rx(r"(^|[^A-Z0-9])(comunicado|aviso|nota|suspensao|cancelamento|prorrogacao)([^A-Z0-9]|$)"), 6, "filename", "filename communication token"),
    Rule("manual_or_regulation", rx(r"(^|[^A-Z0-9])(manual|regulamento|resolucao|portaria|instrucao|anexo)([^A-Z0-9]|$)"), 7, "filename", "filename manual/regulation token"),
]


TEXT_RULES = [
    Rule("demand", rx(r"DEMANDA\s+DE\s+CANDIDATOS\s+POR\s+VAGA|INSCRITOS\s+VAGAS\s+DEMANDA"), 18, "text", "demand table header"),
    Rule("answer_key", rx(r"GABARITOS?\s+(?:OFICIAIS?\s+)?(?:DEFINITIVOS?|PRELIMINARES?)|JUSTIFICATIVAS?\s+DE\s+ALTERA..O\s+DE\s+GABARITO|Gabarito\s+oficial"), 18, "text", "answer-key phrase"),
    Rule("exam", rx(r"Julgue\s+os\s+itens|De acordo com o comando a que cada um dos itens|Caderno\s+[A-Z0-9]|Folha de respostas|UnB/CESPE\s+[–-].*Cargo"), 14, "text", "exam/caderno phrase"),
    Rule("opening_notice", rx(r"torna\s+p[úu]blic[ao]s?\s+a\s+(?:abertura|realiza..o)|abertura\s+de\s+inscri..es|DAS\s+INSCRI..ES\s+NO\s+CONCURSO|remunera..o\s+inicial|DOS\s+CARGOS"), 14, "text", "opening notice phrase"),
    Rule("final_result", rx(r"resultado\s+final\s+no\s+concurso|resultado\s+final\s+do\s+concurso|resultado\s+final\s*[-–]|classifica..o\s+final\s+no\s+concurso|resultado\s+final\s+na"), 15, "text", "final-result phrase"),
    Rule("provisional_result", rx(r"resultado\s+provis[óo]rio|resultado\s+prov\.?|res\.?\s+prov"), 14, "text", "provisional-result phrase"),
    Rule("intermediate_result", rx(r"resultado\s+(?:final|provis[óo]rio)\s+(?:da|das|do|dos|na|nas|no|nos)\s+(?:prova|avalia..o|per.cia|exame|investiga..o|sindic.ncia|t.tulos|capacidade|aptid.o|oral|discursiva|pr.tica)"), 11, "text", "stage-result phrase"),
    Rule("convocation", rx(r"convoca(?:m|dos?|..o|r)?\s+(?:os\s+)?candidatos|convoca..o\s+para|curso\s+de\s+forma..o|matr.cula|nomea..o"), 11, "text", "convocation phrase"),
    Rule("locations", rx(r"locais?\s+e\s+hor[áa]rios?|local\s+e\s+hor[áa]rio|locais?\s+de\s+provas?|endereços?\s+dos\s+locais?"), 12, "text", "location phrase"),
    Rule("erratum", rx(r"retifica(?:m|r|..o)|errata|erro\s+material|sub\s+judice|liminar|decis.o\s+judicial|suspens.o"), 10, "text", "erratum/sub-judice phrase"),
    Rule("appeals", rx(r"recurso|recursos|raz[õo]es\s+para\s+(?:anula..o|manuten..o)|anula..o\s+de\s+quest.o|altera..o\s+de\s+gabarito"), 9, "text", "appeals phrase"),
    Rule("communication", rx(r"comunicado|aviso|nota\s+explicativa|prorroga..o|cancelamento"), 8, "text", "communication phrase"),
    Rule("manual_or_regulation", rx(r"manual\s+do\s+candidato|manual\s+do\s+aluno|regulamento|resolu..o\s+n|portaria\s+n|instru..o\s+normativa"), 10, "text", "manual/regulation phrase"),
    Rule("administrative", rx(r"ata\s+de\s+sess.o|termo\s+aditivo|despacho|publica..o\s+-\s+concurso|documenta..o\s+necess.ria"), 8, "text", "administrative phrase"),
]


REGISTRATION_RE = re.compile(r"\b\d{6,8}\b")
SCORE_RANK_RE = re.compile(r"\b\d{6,8}\b,\s*[^,/]{5,120}?,\s*\d{1,3}[,.]\d{1,2},\s*\d+\b")
CANDIDATE_TABLE_HEADER_RE = rx(r"inscri..o\s+nome|n.mero\s+de\s+inscri..o,\s+nome|nome\s+do\s+candidato")
RESULT_PHRASE_RE = rx(r"resultado\s+(?:final|provis[óo]rio)|classifica..o\s+final")


def normalize_for_rules(text: str) -> str:
    return text.replace("_", " ").replace("-", " ").replace("–", " ")


def stable_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]


def source_pdf_guess(filename: str) -> str:
    if filename.lower().endswith(".pdf.txt"):
        return filename[:-4]
    if filename.lower().endswith(".txt"):
        return filename[:-4] + ".PDF"
    return filename


def concurso_guess(filename: str) -> str:
    stem = filename
    for suffix in [".PDF.txt", ".pdf.txt", ".txt"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = stem.strip()
    patterns = [
        r"^ED(?:ITAL)?[_ ]+(?:COMP[_ ]+)?\d+[_ ]+(?:\d{4}[_ ]+)?([A-Z][A-Z0-9]+(?:[_ ][A-Z0-9]+){0,3})",
        r"^([A-Z]{2,8}(?:[_ ][A-Z]{2,8})?)_",
        r"^(TRE[_ ]?[A-Z]{2}|TSE[_ ]?DF|TREs)",
        r"^([A-Z]{3,12}\d{4})",
    ]
    for pat in patterns:
        match = re.search(pat, stem)
        if match:
            token = match.group(1)
            token = re.sub(r"\s+", "_", token)
            token = re.sub(r"_(RES|RESULTADO|GAB|CARGO|PROVA|DEMANDA|COMUNICADO).*$", "", token, flags=re.I)
            return token.strip("_")
    return ""


def compact_snippet(text: str, max_chars: int = 700) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def find_candidate_snippet(text: str) -> str:
    matches = list(SCORE_RANK_RE.finditer(text))
    if matches:
        start = max(0, matches[0].start() - 300)
        end = min(len(text), matches[0].end() + 700)
        return compact_snippet(text[start:end], 900)
    header = CANDIDATE_TABLE_HEADER_RE.search(text)
    if header:
        start = max(0, header.start() - 200)
        end = min(len(text), header.end() + 800)
        return compact_snippet(text[start:end], 900)
    reg = REGISTRATION_RE.search(text)
    if reg:
        start = max(0, reg.start() - 200)
        end = min(len(text), reg.end() + 600)
        return compact_snippet(text[start:end], 800)
    return ""


def score_document(filename: str, text: str) -> tuple[dict[str, int], list[str]]:
    scores = {doc_type: 0 for doc_type in DOC_TYPES}
    evidence: list[str] = []
    filename_norm = normalize_for_rules(filename)
    text_head = text[:15000]
    text_norm = normalize_for_rules(text_head)

    for rule in FILENAME_RULES:
        if rule.pattern.search(filename_norm):
            scores[rule.doc_type] += rule.weight
            evidence.append(rule.evidence)

    for rule in TEXT_RULES:
        if rule.pattern.search(text_norm):
            scores[rule.doc_type] += rule.weight
            evidence.append(rule.evidence)

    n_reg = len(REGISTRATION_RE.findall(text))
    n_score_rank = len(SCORE_RANK_RE.findall(text))
    if n_score_rank >= 10:
        scores["final_result"] += 7
        evidence.append("many score/rank candidate rows")
    elif n_score_rank >= 2:
        scores["intermediate_result"] += 4
        evidence.append("some score/rank candidate rows")
    elif n_reg >= 20 and RESULT_PHRASE_RE.search(text_norm):
        scores["intermediate_result"] += 5
        evidence.append("many registration numbers plus result phrase")
    elif n_reg >= 50 and not scores["exam"]:
        scores["intermediate_result"] += 2
        evidence.append("many registration-like numbers")

    # Location notices often include many registration numbers but no scores.
    if scores["locations"] and n_score_rank == 0:
        scores["locations"] += 4

    # Opening notices are long and contain registration/payment rules, but should
    # not win over crisp demand/answer-key/exam/final-result labels.
    if scores["opening_notice"] and max(scores["demand"], scores["answer_key"], scores["exam"], scores["final_result"]) >= 14:
        scores["opening_notice"] = max(0, scores["opening_notice"] - 5)

    return scores, evidence


def choose_label(scores: dict[str, int], evidence: list[str], text: str) -> tuple[str, float, int]:
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_label, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score == 0:
        return "other", 0.0, 1

    confidence = min(0.99, 0.45 + best_score / 35 + max(0, best_score - second_score) / 25)
    ambiguous = best_score - second_score <= 3 and second_score >= 8
    needs_llm = int(best_label == "other" or confidence < 0.72 or ambiguous)

    # Result-like documents are high value. Ask LLM to review edge cases.
    n_reg = len(REGISTRATION_RE.findall(text))
    if best_label in {"communication", "erratum", "administrative", "other"} and n_reg >= 10:
        needs_llm = 1
    return best_label, round(confidence, 3), needs_llm


def classify_one(path: Path, text_dir: Path) -> ClassifiedText:
    text = path.read_text(encoding="utf-8", errors="replace")
    filename = path.name
    scores, evidence = score_document(filename, text)
    label, confidence, needs_llm = choose_label(scores, evidence, text)
    n_reg = len(REGISTRATION_RE.findall(text))
    n_score_rank = len(SCORE_RANK_RE.findall(text))
    return ClassifiedText(
        text_id=stable_id(path.relative_to(text_dir)),
        text_path=str(path),
        filename=filename,
        source_pdf_guess=source_pdf_guess(filename),
        concurso_guess=concurso_guess(filename),
        doc_type_rule=label,
        confidence=confidence,
        needs_llm_review=needs_llm,
        score_opening_notice=scores["opening_notice"],
        score_final_result=scores["final_result"],
        score_provisional_result=scores["provisional_result"],
        score_intermediate_result=scores["intermediate_result"],
        score_convocation=scores["convocation"],
        score_locations=scores["locations"],
        score_demand=scores["demand"],
        score_answer_key=scores["answer_key"],
        score_exam=scores["exam"],
        score_erratum=scores["erratum"],
        score_appeals=scores["appeals"],
        score_communication=scores["communication"],
        score_manual_or_regulation=scores["manual_or_regulation"],
        score_administrative=scores["administrative"],
        score_other=scores["other"],
        evidence="; ".join(dict.fromkeys(evidence)),
        text_chars=len(text),
        n_pages_markers=text.count("\f"),
        n_registration_like=n_reg,
        n_score_rank_like=n_score_rank,
        has_candidate_table_header=int(bool(CANDIDATE_TABLE_HEADER_RE.search(text[:20000]))),
        has_result_phrase=int(bool(RESULT_PHRASE_RE.search(text[:20000]))),
        head_snippet=compact_snippet(text[:1500], 700),
        candidate_snippet=find_candidate_snippet(text),
        manual_doc_type="",
        manual_notes="",
        exclude_from_llm="",
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-dir", default=str(DEFAULT_TEXT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    text_dir = Path(args.text_dir)
    out_dir = Path(args.out_dir)
    paths = sorted(p for p in text_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".txt")
    if args.limit:
        paths = paths[: args.limit]

    rows = [classify_one(path, text_dir) for path in paths]
    dict_rows = [asdict(row) for row in rows]
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(ClassifiedText.__dataclass_fields__.keys())
    write_csv(out_dir / "classification_2006_editable.csv", dict_rows, fieldnames)

    counts: dict[str, int] = {}
    review_counts: dict[str, int] = {}
    for row in rows:
        counts[row.doc_type_rule] = counts.get(row.doc_type_rule, 0) + 1
        if row.needs_llm_review:
            review_counts[row.doc_type_rule] = review_counts.get(row.doc_type_rule, 0) + 1

    summary = [
        {
            "doc_type_rule": doc_type,
            "n_files": counts.get(doc_type, 0),
            "n_needs_llm_review": review_counts.get(doc_type, 0),
        }
        for doc_type in DOC_TYPES
        if counts.get(doc_type, 0)
    ]
    write_csv(out_dir / "classification_2006_counts.csv", summary, ["doc_type_rule", "n_files", "n_needs_llm_review"])

    llm_rows = [
        {
            "text_id": row.text_id,
            "filename": row.filename,
            "doc_type_rule": row.doc_type_rule,
            "confidence": row.confidence,
            "evidence": row.evidence,
            "head_snippet": row.head_snippet,
            "candidate_snippet": row.candidate_snippet,
            "llm_doc_type": "",
            "llm_notes": "",
        }
        for row in rows
        if row.needs_llm_review
    ]
    write_csv(
        out_dir / "classification_2006_for_llm_review.csv",
        llm_rows,
        ["text_id", "filename", "doc_type_rule", "confidence", "evidence", "head_snippet", "candidate_snippet", "llm_doc_type", "llm_notes"],
    )

    print(f"Classified files: {len(rows)}")
    print(f"Needs LLM/manual review: {len(llm_rows)}")
    print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
