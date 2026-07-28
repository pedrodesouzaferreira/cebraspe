SRC_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/www.cespe.unb.br/concursos/_antigos/2007"
OUT_ROOT="/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/text/2007"

mkdir -p "$OUT_ROOT"

find "$SRC_ROOT" -type f -iname "*.pdf" |
while IFS= read -r pdf; do
    rel="${pdf#$SRC_ROOT/}"
    out="$OUT_ROOT/${rel}.txt"

    mkdir -p "$(dirname "$out")"

    pdftotext -layout "$pdf" "$out"
done