#!/bin/bash
# End-to-end CEBRASPE pipeline over ALL available years (txt-only).
#   5_classify_all_texts.py       -> Intermediate/classification_all/
#   6_extract_candidate_rows_v2.py-> Intermediate/candidate_extraction_all/
#   7_select_earliest_v2.py       -> Intermediate/candidate_extraction_all/
#
# Run locally for speed (files already materialized in Dropbox).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "[1/3] classifying all texts + selection_type ..."
python3 5_classify_all_texts.py

echo "[2/3] extracting candidate rows (v2 cargo recovery) ..."
python3 6_extract_candidate_rows_v2.py

echo "[3/3] selecting earliest result per applicant ..."
python3 7_select_earliest_v2.py --key-mode applicant
python3 7_select_earliest_v2.py --key-mode application

echo "Done. See Intermediate/classification_all and Intermediate/candidate_extraction_all"
