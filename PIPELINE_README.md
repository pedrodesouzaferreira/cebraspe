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

Note: `10_pdf_to_text.sh` uses a macOS `stat -f` test to skip Dropbox online-only
files; on Linux/FAS RC that test is a harmless no-op (it just converts everything).

## Text tree now MIRRORS the raw tree (update)
`10_pdf_to_text.sh` was rewritten to be a single, idempotent, tree-mirroring
converter. For a PDF at `<Raw Data>/<REL>.pdf` it writes `<Raw Data>/text/<REL>.pdf.txt`,
so `text/` is an exact copy of the raw tree (no more `2002-2008` + `outros` split).
Re-run anytime: it skips any PDF that already has a `.txt` (tolerant to both the
`name.PDF.txt` and stripped `name.txt` conventions), converting only NEW files.
Add the Cebraspe source root to `SRC_ROOTS` once step 3 has downloaded it.

One-time migration of the EXISTING text corpus into the mirror layout:
`bash Code/1b_migrate_text_to_mirror.sh` (moves whole concurso dirs; idempotent).
Run this BEFORE re-running the converter so it doesn't reconvert the ~35k old files.
Order: redownload gaps -> 1b_migrate -> 1_pdf_to_text -> run_pipeline_all.

`5_classify_all_texts.py` reads BOTH layouts (mirror and old), so it works before
or after the migration.

## Import scripts — what downloads what
Downloaders are grouped under `0*` (recurring imports) plus the pre-2002 pair:

- `00_import_cespe.sh` — CESPE legacy site `www.cespe.unb.br`, ALL eras. Part 1: 2002–2019
  from `cespe_urls/urls_YYYY.txt` (idempotent folder check, no Dropbox hydration).
  Part 2: pre-2002 `_antigos/anteriores_2002/…` via Wayback CDX enumeration + live
  download (index pages 500). Flags: FULL=1, SKIP_PRE=1, REFRESH=1.
- `02_import_cebraspe.sh` — modern Cebraspe "encerrados" (424) via the JSON APIs;
  files come from `cdn.cebraspe.org.br` into `Raw Data/cdn.cebraspe.org.br/...`.
- `03_import_cebraspe_gaps.sh` — Cebraspe concursos whose detail API returns
  HTTP 500 (or lists no files). Enumerates their files via the Wayback CDX and
  downloads from the live CDN (Wayback snapshot as fallback).
- `01_unzip_old.sh` — unzip the pre-2002 `.zip` bundles (fetched by `0_import` Part 2)
  before `10_pdf_to_text.sh`.
- OBSOLETE (safe to delete): `0_redownload_gaps.sh` and
  `2_download_anteriores_2002.sh` — both folded into `00_import_cespe.sh`.

Everything lands in `Raw Data/` mirroring the source tree, and `10_pdf_to_text.sh`
then mirrors all of it into `text/`.
