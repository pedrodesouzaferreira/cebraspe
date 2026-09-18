#!/bin/bash
# Convert every PDF to text with pdftotext -layout, MIRRORING the raw tree 1:1.
#
# For a PDF at   <Raw Data>/<REL>.pdf
# it writes text <Raw Data>/text/<REL>.pdf.txt
# so the text/ tree is an exact copy of the raw tree (same folders, same names,
# just .txt appended). No more 2002-2008/outros split.
#
# Idempotent: skips any PDF whose .txt already exists -> re-run anytime to convert
# only the NEW files. Portable (paths relative to this script's location).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
TEXT_ROOT="$RAW/text"

# Source PDF trees to mirror. Add the Cebraspe tree here once step 3 downloads it.
SRC_ROOTS=(
  "$RAW/www.cespe.unb.br/concursos"
  # "$RAW/www.cebraspe.org.br"
)

command -v pdftotext >/dev/null || { echo "ERROR: pdftotext not found (install poppler-utils / poppler)"; exit 1; }

converted=0; skipped=0
for SRC in "${SRC_ROOTS[@]}"; do
  [ -d "$SRC" ] || { echo "skip (absent): $SRC"; continue; }
  while IFS= read -r -d '' pdf; do
    rel="${pdf#"$RAW"/}"              # e.g. www.cespe.unb.br/concursos/_antigos/2006/CID/arquivos/x.PDF
    out="$TEXT_ROOT/${rel}.txt"       # -> text/www.cespe.unb.br/concursos/_antigos/2006/CID/arquivos/x.PDF.txt
    alt="$TEXT_ROOT/${rel%.*}.txt"    # stripped-extension variant (older 'outros' naming)
    if [ -f "$out" ] || [ -f "$alt" ]; then skipped=$((skipped+1)); continue; fi
    mkdir -p "$(dirname "$out")"
    if pdftotext -layout "$pdf" "$out" 2>/dev/null; then
      converted=$((converted+1))
      [ $((converted % 200)) -eq 0 ] && echo "  ...converted $converted so far"
    else
      echo "  FAILED: $rel"
    fi
  done < <(find "$SRC" -type f -iname '*.pdf' -print0)
done
echo "Done. Converted (new): $converted | Skipped (already had .txt): $skipped"
echo "Text tree now mirrors the raw tree under: $TEXT_ROOT"
