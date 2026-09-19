#!/bin/bash
# Unzip archived .zip bundles in-place so pdftotext (10_pdf_to_text.sh) can reach the
# PDFs inside. Each  <dir>/name.zip  is extracted to its own subfolder  <dir>/name/
# (avoids filename collisions when several zips share a folder). The extracted PDFs
# then sit in the raw tree and get mirrored into text/ by the converter.
#
# Idempotent: skips a zip whose target subfolder already exists and is non-empty.
# Skips Dropbox online-only (0-byte) zips and logs them. Handles old Brazilian
# (CP850/Latin-1) filenames when the local unzip supports -O.
# Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
SKIPLOG="$RAW/text/_online_only_zips_skipped.txt"
command -v unzip >/dev/null || { echo "ERROR: unzip not found"; exit 1; }
mkdir -p "$(dirname "$SKIPLOG")"; : > "$SKIPLOG"

# Where to look for zips. Default: pre-2002 archive. Widen to the whole tree by
# setting SRC to "$RAW/www.cespe.unb.br/concursos" (idempotent, so it's safe).
SRC="${1:-$RAW/www.cespe.unb.br/concursos/_antigos/anteriores_2002}"
[ -d "$SRC" ] || { echo "Source not found: $SRC"; exit 1; }

# Does this unzip support -O CHARSET? (Linux Info-ZIP yes; macOS system unzip no)
OCHARSET=""
if printf '' | unzip -O CP850 -l - >/dev/null 2>&1 || unzip -O CP850 -h >/dev/null 2>&1; then
  OCHARSET="-O CP850"
fi

extracted=0; skipped=0; online=0; failed=0
while IFS= read -r -d '' zip; do
  dst="${zip%.[Zz][Ii][Pp]}"                       # strip .zip -> target dir
  if [ -d "$dst" ] && [ -n "$(ls -A "$dst" 2>/dev/null)" ]; then skipped=$((skipped+1)); continue; fi
  # online-only / empty placeholder?
  if [ ! -s "$zip" ] || [ "$(head -c 2 "$zip" 2>/dev/null)" != "PK" ]; then
    online=$((online+1)); printf '%s\n' "${zip#$RAW/}" >> "$SKIPLOG"; continue
  fi
  mkdir -p "$dst"
  if unzip -n -q $OCHARSET -d "$dst" "$zip" >/dev/null 2>&1 || unzip -n -q -d "$dst" "$zip" >/dev/null 2>&1; then
    extracted=$((extracted+1))
    [ $((extracted % 100)) -eq 0 ] && echo "  ...extracted $extracted so far"
  else
    failed=$((failed+1)); rmdir "$dst" 2>/dev/null; echo "  FAILED: ${zip#$RAW/}"
  fi
done < <(find "$SRC" -type f -iname '*.zip' -print0)

echo
echo "Extracted        : $extracted"
echo "Skipped (done)   : $skipped"
echo "Skipped (online) : $online  -> ${SKIPLOG#$RAW/}"
echo "Failed           : $failed"
[ "$online" -gt 0 ] && echo ">> Make the online-only zips 'Available Offline' in Dropbox, then re-run."
echo "Next: run 10_pdf_to_text.sh to convert the extracted PDFs."
