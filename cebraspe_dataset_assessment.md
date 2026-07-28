# CEBRASPE/CESPE Applicant Dataset: Recommended Build Plan

## What the corpus looks like

- The local archive has about 8,275 PDF files under `Data/CEBRASPE/Raw Data/www.cespe.unb.br/concursos`.
- The PDFs are text-readable, so `pdftotext -layout` is the right first extraction tool.
- Filenames contain useful but imperfect labels: `ABT`/opening notice, `RES_FIN`/final result, `RES_PROV`/provisional result, `DEMANDA`, `GAB`, `RET`, `HOMOLOG`, `CONV`, etc.
- A pilot on `TRE_PA2006` and `TSE2006` found several result layouts:
  - prose lists: `inscrição, nome, nota, classificação / ...` under cargo headings;
  - fixed-width tables: columns for inscrição, nome, nota, classificação, cargo;
  - duplicate or near-duplicate result PDFs with slightly different names.

## Recommended target schema

Keep separate normalized tables rather than one very wide table at first.

1. `documents`
   - `pdf_id`, `path`, `concurso_id`, `year_dir`, `filename`, `doc_type`, `pages`, `text_chars`
   - `doc_date`, `edital_number`, `source_url` if recoverable from URL lists

2. `concursos`
   - `concurso_id`, `organ`, `concurso_title`, `year`, `jurisdiction`, `raw_folder`

3. `positions`
   - `concurso_id`, `position_id`, `nivel`, `cargo`, `area`, `especialidade`
   - `vagas`, `vagas_pcd`, `remuneracao`, `jornada`, `requirements`

4. `candidate_results`
   - `candidate_result_id`, `pdf_id`, `concurso_id`, `inscricao`, `nome`
   - `position_id` or raw `cargo`, `localidade`, `etapa`, `resultado_tipo`
   - `nota_final`, stage-specific scores, `classificacao`, `status`
   - `is_final_for_position`, `is_pcd_list`, `is_sub_judice`, `parser`, `confidence`

5. `demand`
   - `concurso_id`, `position_id`, `inscritos`, `vagas`, `demanda`

## Suggested workflow

1. Build a complete PDF manifest.
   - Extract text once and cache it.
   - Classify each document into opening notice, demand, final result, provisional result, answer key, exam, erratum, communication, call notice, or other.

2. Prioritize result documents.
   - Start with `final_result`, then `provisional_result`.
   - Ignore answer keys and exams for applicant rows, but keep them in the manifest.

3. Parse high-frequency layouts deterministically.
   - Use regex/table parsers for slash-separated lists and fixed-width tables.
   - Emit row-level provenance: every row should know the source PDF and parser.

4. Use LLMs for classification and layout rescue, not as the main extractor.
   - Feed an LLM small chunks: first page/title plus candidate-list snippets.
   - Ask it for a JSON layout spec or document metadata.
   - Then run deterministic parsing from that spec.
   - This is much cheaper and easier to audit than asking the LLM to return thousands of candidate rows.

5. Deduplicate and impose document precedence.
   - Many PDFs are retifications, homologations, sub judice notices, and repeated final files.
   - Create candidate keys such as `(concurso_id, inscricao, nome_normalized, cargo_normalized)`.
   - Prefer later/final/homologation documents over provisional documents, while preserving all source rows in a long table.

6. Validate by concurso-year batches.
   - For each concurso, compare parsed row counts with demand PDFs when available.
   - Sample 20 rows per parser layout against the PDF text.
   - Flag documents with many inscrição-like tokens but zero parsed rows.

## Where LLM/HPC fits

On Harvard compute, the best use is a batch classifier/layout assistant:

- input: `pdf_id`, filename, first 2 pages of text, and 1-2 candidate-heavy snippets;
- output: JSON with `doc_type`, `concurso_title`, `organ`, `date`, `layout_type`, expected columns, and whether the document supersedes earlier notices;
- model choice: a cheap local/open model is probably enough for metadata classification, but use a stronger model for hard layouts and edital metadata.

Avoid sending whole long PDFs to the LLM unless deterministic parsing fails.

## Starter code

`cebraspe_audit_pipeline.py` creates:

- `pdf_manifest.csv`
- `doc_type_counts.csv`
- `candidate_rows_pilot.csv`
- `text_cache/*.txt`

Pilot command:

```bash
python3 Data/CEBRASPE/Code/cebraspe_audit_pipeline.py \
  --year 2006 \
  --concurso TRE_PA2006 \
  --concurso TSE2006 \
  --output-dir Data/CEBRASPE/Intermediate/audit_pipeline_pilot_2006_tre_tse
```

