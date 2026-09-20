#!/bin/bash
# Convert every PDF to text with pdftotext -layout, MIRRORING the raw tree 1:1.
#   PDF  <Raw Data>/<REL>.pdf   ->   text  <Raw Data>/text/<REL>.pdf.txt
#
# Idempotent: skips PDFs that already have a .txt (either naming convention).
#
# IMPORTANT (Dropbox online-only): a PDF must be physically on disk to be read.
# macOS reports the full size for "online-only" files and pdftotext's random seeks
# do NOT force a full download, so it fails. We therefore FORCE-HYDRATE each file
# by reading it whole (cat >/dev/null) before converting -- this makes Dropbox
# download it synchronously. Already-local files: the cat is just a fast read.
#
# This means the converter WILL download the PDFs it converts (unavoidable). To
# reclaim space afterwards, re-set the raw folder to "Online only" in Dropbox.
# Set EVICT=1 to try evicting each file right after converting (best-effort).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
TEXT_ROOT="$RAW/text"
SKIPLOG="$TEXT_ROOT/_online_only_skipped.txt"
EVICT="${EVICT:-0}"
SRC_ROOTS=(
  "$RAW/www.cespe.unb.br/concursos"
  "$RAW/cdn.cebraspe.org.br/concursos"
)
command -v pdftotext >/dev/null || { echo "ERROR: pdftotext not found (brew install poppler)"; exit 1; }
: > "$SKIPLOG"

converted=0; skipped=0; online=0; failed=0
for SRC in "${SRC_ROOTS[@]}"; do
  [ -d "$SRC" ] || { echo "skip (absent): $SRC"; continue; }
  while IFS= read -r -d '' pdf; do
    rel="${pdf#"$RAW"/}"
    out="$TEXT_ROOT/${rel}.txt"; alt="$TEXT_ROOT/${rel%.*}.txt"
    if [ -f "$out" ] || [ -f "$alt" ]; then skipped=$((skipped+1)); continue; fi
    cat "$pdf" >/dev/null 2>&1                      # force Dropbox to fully download it
    if [ ! -s "$pdf" ] || [ "$(head -c 5 "$pdf" 2>/dev/null)" != "%PDF-" ]; then
      online=$((online+1)); printf '%s\n' "$rel" >> "$SKIPLOG"; continue
    fi
    mkdir -p "$(dirname "$out")"
    if pdftotext -layout "$pdf" "$out" 2>/dev/null; then
      converted=$((converted+1))
      [ $((converted % 200)) -eq 0 ] && echo "  ...converted $converted"
      [ "$EVICT" = "1" ] && command -v brctl >/dev/null && brctl evict "$pdf" 2>/dev/null
    else
      failed=$((failed+1)); echo "  FAILED (real pdf error): $rel"
    fi
  done < <(find "$SRC" -type f -iname '*.pdf' -print0)
done
echo
echo "Converted (new)          : $converted"
echo "Skipped (already had txt): $skipped"
echo "Could not hydrate/read   : $online  -> ${SKIPLOG#$RAW/}"
echo "Failed (real pdf error)  : $failed"
[ "$online" -gt 0 ] && echo ">> 'Could not hydrate' usually means Dropbox is paused/offline. Resume Dropbox and re-run."
