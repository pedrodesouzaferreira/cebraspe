#!/bin/bash
# Convert documents to text, MIRRORING the raw tree 1:1:
#   <Raw Data>/<REL>.<ext>  ->  <Raw Data>/text/<REL>.<ext>.txt
#
#   .pdf                    -> pdftotext -layout
#   .doc .docx .rtf .htm .html -> textutil (macOS)  ||  libreoffice  ||  pandoc
#
# Idempotent: skips files that already have a .txt (either naming convention).
# Dropbox online-only: force-hydrates each file (cat >/dev/null) before reading, so
# the file is fully downloaded; logs and skips anything that still can't be read.
# EVICT=1 tries to evict each file after converting (best-effort, macOS brctl).
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

# Convert a doc/rtf/html file ($1) to plain text at ($2). Tries several backends.
convert_doc() {
  local s="$1" o="$2" tmp made
  if command -v textutil >/dev/null 2>&1; then
    textutil -convert txt -output "$o" "$s" >/dev/null 2>&1 && [ -s "$o" ] && return 0
  fi
  if command -v libreoffice >/dev/null 2>&1; then
    tmp="$(mktemp -d)"
    libreoffice --headless --convert-to txt:Text --outdir "$tmp" "$s" >/dev/null 2>&1
    made="$(ls "$tmp"/*.txt 2>/dev/null | head -1)"
    [ -n "$made" ] && mv "$made" "$o" 2>/dev/null; rm -rf "$tmp"
    [ -s "$o" ] && return 0
  fi
  if command -v pandoc >/dev/null 2>&1; then
    pandoc -t plain -o "$o" "$s" >/dev/null 2>&1 && [ -s "$o" ] && return 0
  fi
  return 1
}

converted=0; skipped=0; online=0; failed=0
for SRC in "${SRC_ROOTS[@]}"; do
  [ -d "$SRC" ] || { echo "skip (absent): $SRC"; continue; }
  while IFS= read -r -d '' f; do
    rel="${f#"$RAW"/}"
    out="$TEXT_ROOT/${rel}.txt"; alt="$TEXT_ROOT/${rel%.*}.txt"
    if [ -f "$out" ] || [ -f "$alt" ]; then skipped=$((skipped+1)); continue; fi
    cat "$f" >/dev/null 2>&1                        # force Dropbox to fully download it
    if [ ! -s "$f" ]; then online=$((online+1)); printf '%s\n' "$rel" >> "$SKIPLOG"; continue; fi
    ext="$(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z')"
    mkdir -p "$(dirname "$out")"
    ok=0
    case "$ext" in
      pdf)
        if [ "$(head -c 5 "$f" 2>/dev/null)" != "%PDF-" ]; then
          online=$((online+1)); printf '%s\n' "$rel" >> "$SKIPLOG"; continue
        fi
        pdftotext -layout "$f" "$out" 2>/dev/null && ok=1 ;;
      doc|docx|rtf|htm|html)
        convert_doc "$f" "$out" && ok=1 ;;
    esac
    if [ "$ok" = 1 ]; then
      converted=$((converted+1))
      [ $((converted % 200)) -eq 0 ] && echo "  ...converted $converted"
      [ "$EVICT" = "1" ] && command -v brctl >/dev/null && brctl evict "$f" 2>/dev/null
    else
      failed=$((failed+1)); rm -f "$out" 2>/dev/null; echo "  FAILED ($ext): $rel"
    fi
  done < <(find "$SRC" -type f \( -iname '*.pdf' -o -iname '*.doc' -o -iname '*.docx' \
                                 -o -iname '*.rtf' -o -iname '*.htm' -o -iname '*.html' \) \
                 ! -iname 'index.html' -print0)
done
echo
echo "Converted (new)          : $converted"
echo "Skipped (already had txt): $skipped"
echo "Could not hydrate/read   : $online  -> ${SKIPLOG#$RAW/}"
echo "Failed (converter error) : $failed"
[ "$online" -gt 0 ] && echo ">> 'Could not hydrate' = Dropbox paused/offline or file removed. Resume Dropbox and re-run."
