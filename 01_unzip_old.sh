#!/bin/bash
# Unzip .zip bundles FLAT: extract each  <dir>/name.zip  directly into <dir>/ (where
# the zip lives), NOT into a subfolder. Also migrates the OLD layout: if a previous
# run left a  <dir>/name/  subfolder, its files are moved up into <dir>/ and the empty
# subfolder is removed.
#
# Idempotent (unzip -n / keep). Two passes, so NESTED archives are handled: some old
# bundles (e.g. completo.zip) are a "zip of zips" -- pass 1 drops the inner .zip files,
# pass 2 extracts them. Skips Dropbox online-only / non-zip placeholders (logs them).
# For old CP850/Latin-1 entry names that macOS unzip rejects, falls back to ditto
# (Archive Utility) then tar/bsdtar.
#
# CAUTION: flat extraction -> if two zips in the same folder share a filename, the
# first extracted wins. Paths relative to this script (<CEBRASPE>/Code/). Run locally.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
RAW="$CEBRASPE/Raw Data"
SKIPLOG="$RAW/text/_online_only_zips_skipped.txt"
command -v unzip >/dev/null || { echo "ERROR: unzip not found"; exit 1; }
mkdir -p "$(dirname "$SKIPLOG")"; : > "$SKIPLOG"

SRC="${1:-$RAW/www.cespe.unb.br/concursos/_antigos/anteriores_2002}"
[ -d "$SRC" ] || { echo "Source not found: $SRC"; exit 1; }

OCHARSET=""; if unzip -O CP850 -h >/dev/null 2>&1; then OCHARSET="-O CP850"; fi

try_extract() {  # $1=zip  $2=destdir ; returns 0 on success
  local zip="$1" dir="$2" rc
  unzip -n -q $OCHARSET -d "$dir" "$zip" >/dev/null 2>&1; rc=$?; [ "$rc" -le 1 ] && return 0
  unzip -n -q -d "$dir" "$zip" >/dev/null 2>&1; rc=$?; [ "$rc" -le 1 ] && return 0
  command -v ditto  >/dev/null 2>&1 && ditto -x -k "$zip" "$dir"        >/dev/null 2>&1 && return 0
  command -v bsdtar >/dev/null 2>&1 && bsdtar -x -k -f "$zip" -C "$dir" >/dev/null 2>&1 && return 0
  command -v tar    >/dev/null 2>&1 && tar    -x    -f "$zip" -C "$dir" >/dev/null 2>&1 && return 0
  return 1
}

migrate_subfolder() {  # $1=zip : flatten a <dir>/name/ left by the old version
  local zip="$1" dir base name sub
  dir="$(dirname "$zip")"; base="$(basename "$zip")"; name="${base%.[Zz][Ii][Pp]}"; sub="$dir/$name"
  [ -d "$sub" ] || return 1
  while IFS= read -r -d '' f; do
    local rel="${f#$sub/}" tgt="$dir/$rel"
    [ -e "$tgt" ] || { mkdir -p "$(dirname "$tgt")"; mv "$f" "$tgt"; }
  done < <(find "$sub" -type f ! -name '.DS_Store' -print0)
  find "$sub" -name '.DS_Store' -delete 2>/dev/null
  find "$sub" -depth -type d -empty -exec rmdir {} + 2>/dev/null
}

zips_total=0; online=0; failed=0; migrated=0
for pass in 1 2; do
  newly=0
  while IFS= read -r -d '' zip; do
    dir="$(dirname "$zip")"
    [ "$pass" = 1 ] && zips_total=$((zips_total+1))
    [ "$pass" = 1 ] && migrate_subfolder "$zip" && migrated=$((migrated+1))
    if [ ! -s "$zip" ] || [ "$(head -c 2 "$zip" 2>/dev/null)" != "PK" ]; then
      [ "$pass" = 1 ] && { online=$((online+1)); printf '%s\n' "${zip#$RAW/}" >> "$SKIPLOG"; }
      continue
    fi
    before=$(find "$dir" -type f 2>/dev/null | wc -l)
    if try_extract "$zip" "$dir"; then
      after=$(find "$dir" -type f 2>/dev/null | wc -l)
      [ "$after" -gt "$before" ] && newly=$((newly+1))
    else
      [ "$pass" = 1 ] && { failed=$((failed+1)); echo "  FAILED: ${zip#$RAW/}"; }
    fi
  done < <(find "$SRC" -type f -iname '*.zip' -print0)
  [ "$newly" -eq 0 ] && break     # nothing new this pass -> nested archives done
done

echo
echo "Zips found            : $zips_total"
echo "Old subfolders moved  : $migrated"
echo "Skipped (online-only) : $online  -> ${SKIPLOG#$RAW/}"
echo "Failed                : $failed"
echo "Next: run 10_pdf_to_text.sh to convert the extracted PDFs."
