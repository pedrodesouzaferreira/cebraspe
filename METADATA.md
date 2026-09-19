# Metadados (pasta CEBRASPE/Metadata/)

## concursos_master.csv
Um registro por (fonte, concurso). Colunas:
`n, fonte, concurso_id, nome, ano, url, status, fonte_status, n_arquivos, caminho_local, dedup_key, em_ambas_fontes`

- **status** (estado no DISCO):
  - `OK` = pasta presente com documentos
  - `EMPTY` = pasta existe sem documentos
  - `MISSING` = não há pasta local (não baixado)
- **fonte_status** (a página/fonte está viva?), independente do disco:
  - **cebraspe**: sondado via API de detalhe (`apis.cebraspe.org.br/cebraspe/eventos/<url>`):
    `viva` = HTTP 200; `morta` = HTTP 500 (página quebrada, ex.: FUNPRESP_15).
    Resultado (set/2026): 390 vivas, 34 mortas.
  - **cespe**: `nao_verificado`. Motivo: ao tentar sondar (set/2026) o servidor
    legado www.cespe.unb.br passou a dar timeout em TODAS as requisições
    (sobrecarga/rate-limit após o crawl recursivo do pré-2002). Os índices de ano
    de `_antigos/2002..2008` retornam HTTP 500; só as listagens de `anteriores_2002`
    e as páginas de concurso individuais respondem — quando o servidor está no ar.
    Para completar: re-sondar os 38 cespe MISSING/EMPTY quando o servidor voltar
    (sequencial, com espera alta, pra não derrubar de novo).
- **dedup_key**: id normalizado (maiúsculas, sem separadores, ano de 4→2 dígitos)
  para detectar o mesmo concurso nas duas fontes. **em_ambas_fontes** = sim/não.

## concursos_arquivos.csv
Um registro por (concurso, arquivo) — para classificar o que é cada arquivo.
Lista os documentos vistos tanto na árvore raw (pdf/doc/zip) quanto na de texto
convertido, sem duplicar (um arquivo = uma linha, pelo nome do raw). Colunas de
classificação manual: `type, has_names, has_cpf, has_scores`.
