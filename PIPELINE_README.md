# CEBRASPE pipeline — all-years scripts (v2)

Generalizes the 2006 pilot (`2_`, `3_`, `4_`) to every year available under
`Raw Data/text/` (2002..2008 archive folders + the `outros` bucket, which now
also includes 2009-2018 concursos). Works **only on the converted `.txt`**, never
the PDFs.

## Scripts
- `5_classify_all_texts.py` — classify every txt into 15 doc_types AND assign a
  concurso-level `selection_type`. Outputs to `Intermediate/classification_all/`.
- `6_extract_candidate_rows_v2.py` — extract candidate rows (inscricao, nome,
  notas, **cargo**) from result docs. Outputs to `Intermediate/candidate_extraction_all/`.
- `7_select_earliest_v2.py` — collapse to the earliest result per applicant.
- `run_pipeline_all.sh` — runs 5 → 6 → 7 in order.

Run the whole thing (fast on a local disk where Dropbox files are materialized):
```bash
bash Code/run_pipeline_all.sh
```

## selection_type (concurso level)
Decided from the concurso folder name first, then the opening notice — never from
individual filenames (tokens like "REVALIDACAO DE MATRICULA" appear inside ordinary
police concursos, so per-file matching gives false positives).

- `public_job` — concurso publico for a cargo/emprego (default when job language present)
- `scholarship_exchange` — BOLSA / bolsa-premio / intercambio (e.g. IRBRBOLSA, UNBBOLSAS)
- `medical_residency` — RESIDENCIA / MULTIPROF / UNIPROF / PROSAUDE
- `revalidation_proficiency_cert` — REVALIDA, PROFICIENCIA, OAB, VESTIBULAR, CERTIFICACAO
- `other` — no strong signal

Edge decisions:
- `RESIDENCIA...JURIDICA` (DPU legal traineeship) -> `other`, not medical_residency.
- `public_job` is intentionally text-driven so specialized types are not over-assigned.

**Review workflow:** open `selection_type_by_concurso.csv` (~one row per concurso).
To correct any assignment, fill the `selection_type_override` column; downstream
steps should prefer the override when present.

## Cargo/position recovery (v2 improvements)
1. **Column de-pollution** — `pdftotext -layout` merges side-by-side columns onto
   one line. We split each line on runs of >=3 spaces and process segments
   independently, so a header like `1.1.2 PASTOR EVANGELICO:` is isolated from
   unrelated neighbouring-column text.
2. **Broader cargo-header detection** — numbered headers ending in ':',
   `CARGO/EMPREGO/AREA/ESPECIALIDADE:` labels, and standalone Title/UPPER lines
   that are not known section headers. Unusual cargos (PASTOR EVANGELICO, PADRE
   CATOLICO, MUSICO, CAPELAO, medical specialties, ...) are captured without needing
   a keyword list.
3. **Context carry-forward** — the current cargo/nivel/localidade is attached to the
   candidate rows that follow the header.

Validated on `EAOPMS2006` (PMDF health concurso): "PASTOR EVANGELICO" and "PADRE
CATOLICO APOSTOLICO ROMANO" are now captured as positions; ~89% of extracted rows
carry a cargo.

## Notes
- All scripts accept `--text-dir` / `--queue` / `--out-dir`; `5_` and `6_` accept
  `--concurso NAME` (repeatable) and `--limit` for quick subset runs.
- `original_pdf_exists` is left blank on purpose (skips a slow per-file stat on the
  Dropbox placeholder tree); the PDF path is still recorded for provenance.

## Portability (Mac / Dropbox <-> FAS RC)
Every script derives the project root from its own location — it assumes it lives
in `<CEBRASPE>/Code/` and computes `<CEBRASPE>` as the parent of that folder:
- Python: `Path(__file__).resolve().parents[1]`
- Shell:  `CEBRASPE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"`

So there are **no absolute paths**. Move/clone the whole `CEBRASPE` folder anywhere
(Dropbox on your Mac, `/n/…` on FAS RC) and everything resolves, as long as the
layout stays `CEBRASPE/{Code, Raw Data, Intermediate}`. All defaults can still be
overridden with `--text-dir` / `--queue` / `--raw` / `--out-dir` if needed.

Note: `1_pdf_to_text.sh` uses a macOS `stat -f` test to skip Dropbox online-only
files; on Linux/FAS RC that test is a harmless no-op (it just converts everything).
