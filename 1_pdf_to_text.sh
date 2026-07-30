#!/bin/bash
# Convert PDFs -> text with pdftotext -layout. Paths are relative to this
# script's location (assumes this file lives in <CEBRASPE>/Code/).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"

# --- 1) archive year 2008 (mirrors _antigos/2008 -> text/2008) ---
SRC_ROOT="$RAW/www.cespe.unb.br/concursos/_antigos/2008"
OUT_ROOT="$RAW/text/2008"
mkdir -p "$OUT_ROOT"
find "$SRC_ROOT" -type f -iname "*.pdf" |
while IFS= read -r pdf; do
    rel="${pdf#"$SRC_ROOT"/}"
    out="$OUT_ROOT/${rel}.txt"
    mkdir -p "$(dirname "$out")"
    pdftotext -layout "$pdf" "$out"
done

# --- 2) everything outside the 2002-2008 archive -> text/outros ---
SRC_ROOT="$RAW/www.cespe.unb.br/concursos"
OUT_ROOT="$RAW/text/outros"
mkdir -p "$OUT_ROOT"
find "$SRC_ROOT" \
    \( -path "$SRC_ROOT/2002" \
    -o -path "$SRC_ROOT/2003" \
    -o -path "$SRC_ROOT/2004" \
    -o -path "$SRC_ROOT/2005" \
    -o -path "$SRC_ROOT/2006" \
    -o -path "$SRC_ROOT/2007" \
    -o -path "$SRC_ROOT/2008" \) -prune \
    -o -type f -iname "*.pdf" -print |
while IFS= read -r pdf; do
    # Skip Dropbox online-only placeholders (macOS only; harmless no-op on Linux/FAS RC)
    if stat -f "%Sf" "$pdf" 2>/dev/null | grep -qi "offline"; then
        echo "Skipping online-only: $pdf"; continue
    fi
    rel="${pdf#"$SRC_ROOT"/}"
    out="$OUT_ROOT/${rel%.*}.txt"
    mkdir -p "$(dirname "$out")"
    echo "Converting: $rel"
    pdftotext -layout "$pdf" "$out"
done
