========================================================================
COMO RODAR OS SCRIPTS DE IMPORT (download dos concursos)
========================================================================

São 3 scripts de import, todos para rodar LOCALMENTE no seu Mac (terminal),
não dentro do sandbox. Cada um se localiza sozinho (assume que está em
<...>/CEBRASPE/Code/), então pode chamar de qualquer pasta.

Tudo é baixado para dentro de "CEBRASPE/Raw Data/", espelhando a árvore da
origem. Todos são IDEMPOTENTES: rodar de novo só baixa o que falta.

PRÉ-REQUISITOS
--------------
  - wget      (macOS: instale com  brew install wget)
  - curl      (já vem no macOS)
  - python3   (já vem no macOS)
Verifique com:  wget --version ; curl --version ; python3 --version

------------------------------------------------------------------------
1) 00_import_cespe.sh  -> site legado cespe.unb.br (TODAS as épocas)
------------------------------------------------------------------------
O que faz:
  Parte 1: concursos de 2002-2019, lidos de cespe_urls/urls_YYYY.txt
           (baixa a página-capa e tudo que ela linka). Pula concursos que
           já têm arquivos no disco (checagem por metadados, SEM hidratar
           o Dropbox).
  Parte 2: acervo pré-2002 (_antigos/anteriores_2002). As páginas de índice
           dão erro 500, então a lista de arquivos é obtida da Wayback (CDX)
           e baixada do site ao vivo, com fallback para o snapshot da Wayback.
           Esses arquivos são quase todos .zip.

Onde cai:  Raw Data/www.cespe.unb.br/concursos/...

Rodar:
    bash "CEBRASPE/Code/00_import_cespe.sh"

Opções (variáveis de ambiente):
    FULL=1     bash .../00_import_cespe.sh   # re-roda o wget mesmo nos que já existem
                                      # (completa concursos baixados pela metade)
    SKIP_PRE=1 bash .../00_import_cespe.sh   # pula a Parte 2 (pré-2002)
    REFRESH=1  bash .../00_import_cespe.sh   # re-consulta a lista da Wayback (Parte 2)

Saída: uma linha por concurso, ex.:
    downloading SGAAC2007 ... OK (42 files) -> www.cespe.unb.br/concursos/SGAAC2007/
    downloading _antigos/2002/cbmdf ... EMPTY (dead/moved at source)
No fim, um resumo (baixados / pulados / vazios).

DEPOIS: os arquivos pré-2002 são .zip. Rode  bash CEBRASPE/Code/01_unzip_old.sh
para descompactar antes da conversão (10_pdf_to_text.sh).

------------------------------------------------------------------------
2) 02_import_cebraspe.sh  -> site novo cebraspe.org.br (encerrados)
------------------------------------------------------------------------
O que faz:
  Descobre os ~424 concursos "encerrados" pela API do Cebraspe e baixa os
  arquivos do CDN. Também gera dois arquivos de apoio em cespe_urls/:
  urls_cebraspe_encerrado.txt (lista de arquivos) e
  cebraspe_encerrado_index.tsv (índice: eventoURL, ano, nome, nº de arquivos).

Onde cai:  Raw Data/cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/...

Rodar:
    bash "CEBRASPE/Code/02_import_cebraspe.sh"

Observação: baixa bastante coisa (dezenas de milhares de PDFs no total).
É idempotente (wget -nc): rodar de novo pula o que já baixou.

------------------------------------------------------------------------
3) 03_import_cebraspe_gaps.sh  -> recupera lacunas do Cebraspe
------------------------------------------------------------------------
O que faz:
  ~39 concursos do Cebraspe têm a API de detalhe quebrada (HTTP 500) ou sem
  arquivos, então o 0b não os pega. Este script acha esses "buracos", enumera
  os arquivos deles pela Wayback (CDX) e baixa do CDN ao vivo (com fallback
  para o snapshot da Wayback). Gera cespe_urls/cebraspe_gaps_report.tsv.

Onde cai:  Raw Data/cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/...

Rodar (SEMPRE depois do 0b):
    bash "CEBRASPE/Code/03_import_cebraspe_gaps.sh"

------------------------------------------------------------------------
ORDEM RECOMENDADA
------------------------------------------------------------------------
    bash CEBRASPE/Code/00_import_cespe.sh          # cespe.unb.br (2002-2019 + pré-2002)
    bash CEBRASPE/Code/01_unzip_old.sh          # descompacta os .zip do pré-2002
    bash CEBRASPE/Code/02_import_cebraspe.sh   # cebraspe.org.br (424)
    bash CEBRASPE/Code/03_import_cebraspe_gaps.sh  # lacunas do Cebraspe

Depois de baixar, a conversão para texto é com  10_pdf_to_text.sh.

NOTAS
-----
- Os scripts baixam para o Dropbox. Manter os PDFs "somente online" economiza
  espaço, mas para CONVERTER (10_pdf_to_text.sh) eles precisam estar no disco.
- Rodar de novo qualquer script é seguro: eles só completam o que falta.
- "EMPTY"/"dead" = a fonte não serve mais aquele concurso (erro 500 ou removido).
