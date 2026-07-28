SRC_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/www.cespe.unb.br/concursos/_antigos/2008"
OUT_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/text/2008"

mkdir -p "$OUT_ROOT"

find "$SRC_ROOT" -type f -iname "*.pdf" |
while IFS= read -r pdf; do
    rel="${pdf#$SRC_ROOT/}"
    out="$OUT_ROOT/${rel}.txt"

    mkdir -p "$(dirname "$out")"

    pdftotext -layout "$pdf" "$out"
done

SRC_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/www.cespe.unb.br/concursos"
OUT_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/text/outros"

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
    if stat -f "%Sf" "$pdf" | grep -qi "offline"; then
        echo "Skipping online-only: $pdf"
        continue
    fi

    rel="${pdf#"$SRC_ROOT"/}"
    out="$OUT_ROOT/${rel%.*}.txt"

    mkdir -p "$(dirname "$out")"
    echo "Converting: $rel"
    pdftotext -layout "$pdf" "$out"
done