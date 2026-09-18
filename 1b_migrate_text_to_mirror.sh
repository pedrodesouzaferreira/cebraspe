#!/bin/bash
# Merge OLD text layout (text/{2002..2008,outros}/<concurso>/...) into the mirror
# text/www.cespe.unb.br/concursos/...  Needs NO hydration (only touches .txt).
#
# Safe MERGE + CLEANUP (run even after the converter already built part of the mirror):
#   - concurso not yet in mirror         -> move the whole dir (fast)
#   - concurso partially in mirror       -> move only the missing .txt files
#   - a .txt already present in mirror    -> delete the old duplicate (data is safe)
# Never overwrites a mirror file. At the end the old folders are gone; only
# text/www.cespe.unb.br remains. Idempotent.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
TEXT_ROOT="$CEBRASPE/Raw Data/text"
DEST="$TEXT_ROOT/www.cespe.unb.br/concursos"
mkdir -p "$DEST/_antigos"

moved_dirs=0; moved_files=0; dropped_dups=0

merge_concurso() {  # $1=src concurso dir  $2=dest concurso dir
  local src="$1" dst="$2"
  if [ ! -e "$dst" ]; then
    mkdir -p "$(dirname "$dst")"; mv "$src" "$dst" && moved_dirs=$((moved_dirs+1)); return
  fi
  while IFS= read -r -d '' f; do
    local rel="${f#$src/}"
    local target="$dst/$rel"
    if [ -e "$target" ]; then rm -f "$f"; dropped_dups=$((dropped_dups+1))
    else mkdir -p "$(dirname "$target")"; mv "$f" "$target" && moved_files=$((moved_files+1)); fi
  done < <(find "$src" -type f -name '*.txt' -print0)
}

cleanup_old() {  # $1 = old top dir (year or outros)
  local d="$1"
  [ -d "$d" ] || return
  find "$d" -name '.DS_Store' -delete 2>/dev/null
  # only remove if no .txt remain (safety)
  if [ -z "$(find "$d" -type f -name '*.txt' -print -quit)" ]; then rm -rf "$d"; fi
}

for y in 2002 2003 2004 2005 2006 2007 2008; do
  [ -d "$TEXT_ROOT/$y" ] || continue
  for c in "$TEXT_ROOT/$y"/*; do [ -d "$c" ] || continue
    merge_concurso "$c" "$DEST/_antigos/$y/$(basename "$c")"; done
  cleanup_old "$TEXT_ROOT/$y"
done
if [ -d "$TEXT_ROOT/outros" ]; then
  for c in "$TEXT_ROOT/outros"/*; do [ -d "$c" ] || continue
    merge_concurso "$c" "$DEST/$(basename "$c")"; done
  cleanup_old "$TEXT_ROOT/outros"
fi

echo "Concurso dirs moved whole : $moved_dirs"
echo "Missing files merged      : $moved_files"
echo "Old duplicates removed    : $dropped_dups"
echo "Remaining non-www entries in text/:"
ls -1A "$TEXT_ROOT" | grep -v '^www.cespe.unb.br$' || echo "  (none - clean!)"
