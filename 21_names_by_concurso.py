#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
21_names_by_concurso.py  —  Colapsa a base de nomes para nivel NOME x CONCURSO.

Le a saida do 20_extract_names.py (Clean Data/nomes_extraidos.*), que esta no nivel
nome x concurso x arquivo, e agrega para uma linha por (concurso, nome): ou seja,
"esta pessoa aparece neste concurso". Isso e' o que serve para contar em quantos
concursos distintos cada pessoa se candidatou.

Deduplicacao: por (concurso, nome normalizado) -- ignora acento e caixa, para o
mesmo nome escrito de formas diferentes nao contar duas vezes no mesmo concurso.

SAIDA (em Clean Data/)
----------------------
Clean Data/nomes_por_concurso.parquet   e   .csv
Colunas: name, concurso, year, n_arquivos
  name       = nome (primeira grafia vista)
  concurso   = concurso_id
  year       = ano
  n_arquivos = em quantos arquivos daquele concurso a pessoa apareceu

USO
---
    python3 21_names_by_concurso.py
(rode o 20_extract_names.py antes, para gerar Clean Data/nomes_extraidos.*)
"""
import os, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CEBRASPE = os.path.dirname(HERE)
OUTDIR = os.path.join(CEBRASPE, "Clean Data")
IN_PARQUET = os.path.join(OUTDIR, "nomes_extraidos.parquet")
IN_CSV     = os.path.join(OUTDIR, "nomes_extraidos.csv")
OUT_PQ = os.path.join(OUTDIR, "nomes_por_concurso.parquet")
OUT_CSV = os.path.join(OUTDIR, "nomes_por_concurso.csv")

def norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode().upper().strip()

def main():
    import pandas as pd
    src = IN_PARQUET if os.path.exists(IN_PARQUET) else IN_CSV
    if not os.path.exists(src):
        print("Nao achei Clean Data/nomes_extraidos.* -- rode 20_extract_names.py primeiro.")
        sys.exit(1)
    print(f"Lendo: {src}")
    df = pd.read_parquet(src) if src.endswith(".parquet") else pd.read_csv(src, dtype=str, keep_default_na=False)
    print(f"  linhas (nome x concurso x arquivo): {len(df):,}")

    df["_key"] = df["name"].map(norm)
    # 1 linha por (concurso, nome normalizado)
    g = df.groupby(["concurso", "_key"], sort=False)
    out = g.agg(
        name=("name", "first"),
        year=("year", "first"),
        n_arquivos=("file", "nunique"),
    ).reset_index()
    out = out[["name", "concurso", "year", "n_arquivos"]]
    print(f"  linhas (nome x concurso)          : {len(out):,}")

    os.makedirs(OUTDIR, exist_ok=True)
    out.to_parquet(OUT_PQ, index=False)
    out.to_csv(OUT_CSV, index=False)
    print(f"Parquet: {OUT_PQ}")
    print(f"CSV    : {OUT_CSV}")
    # panorama: quantas pessoas (nome unico) e distribuicao de concursos por pessoa
    per_person = out.groupby(out["name"].map(norm))["concurso"].nunique()
    print(f"\nPessoas distintas (por nome): {per_person.size:,}")
    print(f"Aparecem em >1 concurso     : {(per_person>1).sum():,}")
    print(f"Max concursos p/ uma pessoa : {per_person.max()}")

if __name__ == "__main__":
    main()
