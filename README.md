# cebraspe

Scrapes the public archive of Brazilian civil-service exam results published by CESPE/Cebraspe (the exam board of the University of Brasília, 1997–present), converts about 60,000 PDFs to text, classifies each document, and extracts the lists of candidates into a tidy dataset of *who applied to which exam in which year*.

Built for **"The Value of Government Jobs"** (Pedro Ferreira, Harvard Kennedy School, dissertation in progress). The downloaded documents and the extracted dataset are not in the repository; the scripts recreate them.

## Pipeline

Run from a terminal on macOS or Linux. Every step is idempotent: re-running only completes what is missing.

| Step | Script | What it does |
|---|---|---|
| 00 | `00_import_cespe.sh` | Downloads every exam from the legacy site `cespe.unb.br` (2002–2019 from the per-year URL lists in `Raw Data/cespe_urls/urls_YYYY.txt`, which are not in this repo; the pre-2002 archive via the Wayback Machine CDX index, with live-site download and Wayback fallback). |
| 01 | `01_unzip_old.sh` | Unpacks the pre-2002 `.zip` bundles. |
| 02 | `02_import_cebraspe.sh` | Discovers the ~424 closed exams on the current site `cebraspe.org.br` through its API and downloads their files from the CDN; writes a file list and an index (`eventoURL`, year, name, number of files) to `Raw Data/cespe_urls/`. |
| 03 | `03_import_cebraspe_gaps.sh` | Recovers the ~39 exams whose API detail page is broken, by enumerating their files on the Wayback Machine and downloading from the live CDN with Wayback fallback. |
| 10 | `10_pdf_to_text.sh` | Converts every document to text, mirroring the raw tree one-to-one (`pdftotext -layout` for PDFs; `textutil`, LibreOffice or pandoc for .doc/.docx/.rtf/.html). Handles Dropbox online-only files. |
| 11 | `11_classify_files.py` | Classifies each text file (type, subtype, whether it contains candidate names or scores) into `Metadata/concursos_arquivos.csv`. Rows classified by hand are flagged `human = 1` and never overwritten. |
| 20 | `20_extract_names.py` | Parses the candidate lists (records separated by `/`, fields by `,`) and extracts names, requiring a registration number in each record to filter out prose. Output: one row per name x exam x file. |
| 21 | `21_names_by_concurso.py` | Collapses to one row per (exam, name), deduplicating on accent- and case-insensitive names, so each person can be counted across the exams they entered. |

## Requirements

- `wget`, `curl`, `python3` (macOS: `brew install wget`)
- `pdftotext` (poppler) for step 10; `textutil` ships with macOS, LibreOffice or pandoc are optional fallbacks
- Python: `pandas`, `pyarrow`

```bash
pip install pandas pyarrow
```

## Running

```bash
bash 00_import_cespe.sh            # legacy site, all years
bash 01_unzip_old.sh               # pre-2002 archives
bash 02_import_cebraspe.sh         # current site
bash 03_import_cebraspe_gaps.sh    # fill the gaps (always after 02)
bash 10_pdf_to_text.sh             # PDFs -> text
python3 11_classify_files.py       # classify documents
python3 20_extract_names.py        # extract candidate names
python3 21_names_by_concurso.py    # one row per exam x candidate
```

Options for `00_import_cespe.sh` are environment variables: `FULL=1` re-runs `wget` even for exams already on disk, `SKIP_PRE=1` skips the pre-2002 archive, `REFRESH=1` re-queries the Wayback file list. `11_classify_files.py N` classifies only the first N rows.

Paths resolve relative to the script location; the expected layout is `<CEBRASPE>/Code/` (this repo), `<CEBRASPE>/Raw Data/`, `<CEBRASPE>/Raw Data/text/`, `<CEBRASPE>/Metadata/` and `<CEBRASPE>/Clean Data/`.

## Output

`Clean Data/nomes_extraidos.parquet` (name x exam x file) and `Clean Data/nomes_por_concurso.parquet` (name x exam, with the number of files the name appeared in). The source documents are public records published by the exam board.
