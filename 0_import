cd "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2002.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2003.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2004.txt"
wget --recursive --level=inf --no-parent --ignore-case -e robots=off --no-clobber --wait=1 --random-wait --limit-rate=500k -i "/Users/pedroferreira/Dropbox (Personal)/MY PROJECTS/CONCURSOS/Data/CEBRASPE/Raw Data/cespe_urls/urls_2005.txt"


curl -sG "http://web.archive.org/cdx/search/cdx" \
  --data-urlencode "url=cespe.unb.br/concursos*" \
  --data-urlencode "filter=original:.*/2002/.*\.[Pp][Dd][Ff]$" \
  --data-urlencode "collapse=urlkey" \
  --data-urlencode "fl=original" \
  --data-urlencode "output=text" \
  > ~/Downloads/cespe_pdfs_2002.txt
wc -l ~/Downloads/cespe_pdfs_2002.txt
head -30 ~/Downloads/cespe_pdfs_2002.txt