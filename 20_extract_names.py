#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20_extract_names.py  —  Extrai nomes de candidatos dos arquivos marcados has_names=1.

Percorre Metadata/concursos_arquivos.csv, e para cada arquivo com has_names==1 abre
o .txt correspondente em Raw Data/text/ e extrai os nomes.

COMO ELE ACHA OS NOMES (simples, como pedido)
---------------------------------------------
As listas de candidatos vem em REGISTROS separados por barra "/", e cada registro
tem CAMPOS separados por virgula, ex.:
    10006548, Luiz Henrique Amorim de Jesus Junior, 83.18, 40 / 10005113, Ana Silva / ...
O nome e' sempre o campo ALFABETICO (o resto e' numero de inscricao, notas, etc.).
Entao, para cada registro:
  1. exige que o registro tenha um numero de inscricao (6-9 digitos) -> filtra prosa;
  2. quebra por virgula e escolhe o campo que parece um nome (Title Case/MAIUSCULAS,
     2+ palavras, sem palavras de prosa da stoplist).
Arquivos sem barras sao quebrados por linha e tratados igual. Nomes sao deduplicados
por arquivo.

SAIDA (em Clean Data/)
----------------------
Clean Data/nomes_extraidos.parquet   e   Clean Data/nomes_extraidos.csv
Colunas: name, concurso, file, year, directory
  name      = nome do candidato
  concurso  = concurso_id
  file      = nome do arquivo (como em Raw Data)
  year      = ano
  directory = pasta do arquivo (caminho relativo, sem o nome do arquivo)

USO
---
    python3 20_extract_names.py          # processa TODOS os has_names=1
    python3 20_extract_names.py 500      # so os 500 primeiros has_names=1 (teste)
"""
import csv, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CEBRASPE = os.path.dirname(HERE)
CSV_IN  = os.path.join(CEBRASPE, "Metadata", "concursos_arquivos.csv")
TEXT    = os.path.join(CEBRASPE, "Raw Data", "text")
OUTDIR  = os.path.join(CEBRASPE, "Clean Data")
OUT_CSV = os.path.join(OUTDIR, "nomes_extraidos.csv")
OUT_PQ  = os.path.join(OUTDIR, "nomes_extraidos.parquet")

INSCR = re.compile(r'\b\d{6,9}\b')                 # numero de inscricao do candidato
CONN  = {"DE","DA","DO","DAS","DOS","E","DI","DEL","DELLA","DELLO","VAN","VON","Y","DU","D"}
# palavras que aparecem em prosa de edital -> se o "nome" contem alguma, descarta
STOP  = {"NUMERO","INSCRICAO","NOME","CANDIDATO","CANDIDATA","CANDIDATOS","ORDEM","ALFABETICA",
"RESULTADO","FINAL","PROVA","PROVAS","NOTA","NOTAS","NIVEL","CLASSIFICACAO","CLASSIFICADOS",
"SEGUINTE","CONCURSO","PUBLICO","PROCESSO","DECISAO","JUDICIAL","CUMPRIMENTO","MESA","CADEIRA",
"TEMPO","ADICIONAL","OCULOS","BONE","PORTADORES","RELACAO","CARGO","VAGAS","VAGA","SELETIVO",
"OBJETIVA","DISCURSIVA","TITULOS","DIARIO","OFICIAL","EDITAL","AUTOS","AGRAVO","INSTRUMENTO",
"SUBJUDICE","ATENCAO","RESOLVE","PUBLICAR","TURNO","MANHA","TARDE","NOITE","PRESIDENTE",
"COMISSAO","AVENIDA","RUA","PRACA","BAIRRO","CIDADE","ENDERECO","LOCAL","SALA"}

def norm(s): return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().upper()

def txt_path(rel):
    for c in (os.path.join(TEXT, rel + ".txt"), os.path.join(TEXT, os.path.splitext(rel)[0] + ".txt")):
        if os.path.exists(c): return c
    return None

def clean_name(s):
    s = " ".join(s.split())
    s = re.match(r"^[^\d]*", s).group(0).strip(" .,-–—;:•()")   # corta no 1o digito
    return " ".join(s.split())

def looks_name(s):
    if not s or len(s) > 70: return False
    toks = s.split()
    if not (2 <= len(toks) <= 8): return False
    if norm(toks[0]) in CONN: return False                       # nao comeca com conector
    for t in toks:
        nt = norm(t)
        if nt in STOP: return False                              # palavra de prosa
        if nt in CONN: continue                                  # conector minusculo ok
        if not t[0].isupper(): return False                      # nao-conector: Title/UPPER
        if not re.match(r"^[A-Za-zÀ-ÿ'’.\-]+$", t): return False
    return sum(c.isalpha() for c in s) / max(1, len(s)) > 0.75

def extract_names(text):
    recs = text.split("/") if text.count("/") >= 5 else text.splitlines()
    out = []
    for rec in recs:
        if not INSCR.search(rec):                                # registro precisa ter inscricao
            continue
        best = None
        for f in re.split(r'[;,]', rec):
            c = clean_name(f)
            if looks_name(c) and (best is None or len(c) > len(best)):
                best = c
        if best:
            out.append(best)
    seen, uniq = set(), []                                       # dedup por arquivo
    for nm in out:
        k = norm(nm)
        if k not in seen:
            seen.add(k); uniq.append(nm)
    return uniq

def main():
    limit = None
    if len(sys.argv) > 1 and sys.argv[1].lower() not in ("all","todos","tudo"):
        try: limit = int(sys.argv[1])
        except ValueError: print("Uso: python3 20_extract_names.py [N|all]"); sys.exit(2)

    os.makedirs(OUTDIR, exist_ok=True)
    with open(CSV_IN, newline="", encoding="utf-8") as f:
        targets = [r for r in csv.DictReader(f) if r.get("has_names") == "1"]
    if limit is not None:
        targets = targets[:limit]
    print(f"Arquivos has_names=1 a processar: {len(targets)}")

    fout = open(OUT_CSV, "w", newline="", encoding="utf-8")
    w = csv.writer(fout)
    w.writerow(["name","concurso","file","year","directory"])

    files_done = files_with_names = total_names = no_txt = 0
    for r in targets:
        files_done += 1
        p = txt_path(r["caminho_rel"])
        if not p:
            no_txt += 1
        else:
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                text = ""
            names = extract_names(text)
            if names:
                files_with_names += 1
                directory = os.path.dirname(r["caminho_rel"])
                for nm in names:
                    w.writerow([nm, r["concurso_id"], r["arquivo"], r["ano"], directory])
                    total_names += 1
        if files_done % 500 == 0:
            print(f"  ... {files_done}/{len(targets)} arquivos | {total_names} nomes", flush=True)
    fout.close()

    print(f"\nArquivos processados : {files_done}")
    print(f"  com nomes extraidos: {files_with_names}")
    print(f"  sem txt            : {no_txt}")
    print(f"Total de nomes (linhas): {total_names}")
    print(f"CSV: {OUT_CSV}")

    # parquet (em blocos, baixa memoria) via pyarrow
    try:
        import pandas as pd, pyarrow as pa, pyarrow.parquet as pq
        writer = None
        for chunk in pd.read_csv(OUT_CSV, dtype=str, chunksize=200_000, keep_default_na=False):
            tbl = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(OUT_PQ, tbl.schema, compression="snappy")
            writer.write_table(tbl)
        if writer: writer.close()
        print(f"Parquet: {OUT_PQ}")
    except Exception as e:
        print(f"(parquet nao gerado - instale: pip install pandas pyarrow. {type(e).__name__}: {e})")

if __name__ == "__main__":
    main()
