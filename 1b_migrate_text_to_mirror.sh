#!/bin/bash
# One-time migration: move the existing text/ (old 2002-2008 + outros layout) into
# the mirror layout text/www.cespe.unb.br/concursos/... so it matches the raw tree
# and the rewritten 1_pdf_to_text.sh won't re-convert anything.
#   text/<YYYY>/<concurso>/...   -> text/www.cespe.unb.br/concursos/_antigos/<YYYY>/<concurso>/...
#   text/outros/<concurso>/...   -> text/www.cespe.unb.br/concursos/<concurso>/...
# Moves whole concurso directories (fast). Idempotent: skips if destination exists.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CEBRASPE="$(cd "$HERE/.." && pwd)"
TEXT_ROOT="$CEBRASPE/Raw Data/text"
DEST="$TEXT_ROOT/www.cespe.unb.br/concursos"

moved=0; kept=0
for y in 2002 2003 2004 2005 2006 2007 2008; do
  [ -d "$TEXT_ROOT/$y" ] || continue
  mkdir -p "$DEST/_antigos/$y"
  for c in "$TEXT_ROOT/$y"/*; do
    [ -e "$c" ] || continue
    bn="$(basename "$c")"
    if [ -e "$DEST/_antigos/$y/$bn" ]; then echo "skip (exists): _antigos/$y/$bn"; kept=$((kept+1))
    else mv "$c" "$DEST/_antigos/$y/$bn" && moved=$((moved+1)); fi
  done
done
if [ -d "$TEXT_ROOT/outros" ]; then
  mkdir -p "$DEST"
  for c in "$TEXT_ROOT/outros"/*; do
    [ -e "$c" ] || continue
    bn="$(basename "$c")"
    if [ -e "$DEST/$bn" ]; then echo "skip (exists): $bn"; kept=$((kept+1))
    else mv "$c" "$DEST/$bn" && moved=$((moved+1)); fi
  done
fi
echo "Migrated concurso dirs: $moved | already-present: $kept"
echo "Old empty folders text/{2002..2008,outros} can be deleted by hand (Dropbox blocks rm here)."
