#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_classify_files.py  —  Classifica automaticamente os arquivos de concursos.

Preenche, em Metadata/concursos_arquivos.csv, as colunas:
    type, subtype, has_names, has_cpf, has_scores
lendo APENAS os .txt convertidos em  Raw Data/text/  (nunca os PDFs originais).

PROTECAO DA CLASSIFICACAO HUMANA
--------------------------------
Adiciona uma coluna  human :
    human = 1  -> linha classificada por VOCE (a mao). O script NUNCA sobrescreve.
    human = 0  -> linha classificada pelo codigo. Pode ser sobrescrita numa nova rodada.
Na primeira vez que roda, marca human=1 em toda linha que ja tem 'type' preenchido
(as suas classificacoes manuais atuais) e human=0 no resto.

USO
---
    python3 11_classify_files.py            # classifica TODAS as linhas elegiveis
    python3 11_classify_files.py 100        # so as 100 PRIMEIRAS linhas do CSV
    python3 11_classify_files.py 200        # so as 200 primeiras, etc.

"Primeiras" = ordem em que as linhas aparecem no CSV (coluna n). Dentro desse
recorte, linhas com human=1 sao puladas (mantidas intactas); as demais sao
(re)classificadas.

QUALIDADE (validado contra 3 concursos classificados a mao, 124 arquivos)
    has_cpf   ~100%   has_scores ~95%   has_names ~90%
    type/subtype: best-effort (~2/3). Revise e va marcando human=1 no que corrigir;
    quanto mais voce corrigir, melhor da pra afinar as regras depois.
"""
import csv, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CEBRASPE = os.path.dirname(HERE)
CSV  = os.path.join(CEBRASPE, "Metadata", "concursos_arquivos.csv")
TEXT = os.path.join(CEBRASPE, "Raw Data", "text")

COLS_BASE = ["n","fonte","ano","concurso_id","arquivo","ext","presente_raw",
             "presente_txt","caminho_rel","type","subtype","has_names",
             "has_cpf","has_scores","notes"]
CLASS_COLS = ["type","subtype","has_names","has_cpf","has_scores"]

# ---------- deteccao de conteudo (regex) ----------
CPF   = re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b')
CPFM  = re.compile(r'[\*x]{2,3}\.?\d{3}\.\d{3}-?[\*x]{2}', re.I)   # cpf mascarado ***.123.456-**
SCORE = re.compile(r'\b\d{1,3}[.,]\d{2}\b')                        # nota tipo 85,50 ou 85.50
NAME  = re.compile(r'\b[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ][a-zá-úâ-ûã-õ]+'
                   r'(?:\s+(?:d[aeo]s?|e|[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ][a-zá-úâ-ûã-õ]+)){1,5}'
                   r'\s+[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ][a-zá-úâ-ûã-õ]+\b')

# limiares calibrados no gold
SLASH_PER_KB = 6      # listas compactadas de candidatos usam " / " entre registros
NAME_MIN     = 40     # nº de nomes-completos p/ considerar "lista de nomes"
SCORE_MIN    = 60     # nº de notas p/ has_scores (so vale se ja tem nomes)
CPF_MIN      = 6      # nº de CPFs p/ has_cpf

def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().upper()

def txt_path(rel):
    for c in (os.path.join(TEXT, rel + ".txt"),
              os.path.join(TEXT, os.path.splitext(rel)[0] + ".txt")):
        if os.path.exists(c):
            return c
    return None

def analyze(fname, text):
    """Retorna (type, subtype, has_names, has_cpf, has_scores)."""
    F = norm(fname); H = norm(text[:8000]); n = len(text) or 1
    slash_kb = text.count("/") / (n / 1000.0)
    body = text[:2_000_000]
    nmatch = len(NAME.findall(body))
    smatch = len(SCORE.findall(body))
    cpf    = len(CPF.findall(text)) + len(CPFM.findall(text))
    namelist = slash_kb >= SLASH_PER_KB or nmatch >= NAME_MIN

    def hf(*k): return any(x in F for x in k)   # no nome do arquivo
    def hh(*k): return any(x in H for x in k)   # no inicio do conteudo

    typ, sub = None, ""
    # 1) gabarito / padrao de resposta / espelho
    if hf("GABARIT","PADRAO_DE_RESPOSTA","PADROES","ESPELHO","JUSTIFICATIV") \
       or hh("PADRAO DE RESPOSTA","GABARITO OFICIAL","ESPELHO DE PROVA"):
        typ = "gabarito"
        sub = "discursiva" if hf("DISC","RESPOSTA","REDACAO","ESPELHO","JUSTIF") \
                              or hh("DISCURSIV","PADRAO DE RESPOSTA") else "objetiva"
        if hf("DEFINITIV","ALTERAC","RETIFIC"): sub = "alteracao"
    # 2) candidato x vaga
    elif hf("DEMANDA") or (hh("CANDIDATO") and hh("POR VAGA","CONCORRENCIA")):
        typ = "candidatovaga"
    # 3) inscricao
    elif hf("INSC") or hh("DEFERIMENTO DE INSCRICAO","PEDIDOS DE INSCRICAO"):
        typ = "inscricao"
        sub = "final" if hf("FINAL","DEFINITIV") or hh("FINAL","DEFINITIV") else "provisorio"
    # 4) resultado — por lista de nomes OU por palavra-chave
    elif namelist or hf("RES_","RESULT","_RES_","CLASSIF","CONVOCA","HOMOLOG","APROVAD","DIVULG") \
         or hh("RESULTADO","CLASSIFICAD","CLASSIFICACAO","APROVADOS","CONVOCAC","HOMOLOGAC"):
        typ = "resultado"
    # 5) prova
    elif hf("PROVA","CADERNO") or re.search(r'_\d{2,3}_(0\d|DISC)\b', F) or F.endswith("_DISC") \
         or hh("PROVA OBJETIVA","CADERNO DE PROVA","PROVA DISCURSIVA"):
        typ = "prova"
        sub = "discursiva" if hf("DISC","REDACAO") or hh("DISCURSIV","REDACAO") else "objetiva"
    # 6) edital / comunicado / aviso / portaria
    elif hf("ED_","EDITAL","COMUNICADO","AVISO","_RET","RET_","ABERTURA","BANCA","LOCAI","PORTARIA","PRORROG") \
         or hh("EDITAL N","COMUNICADO","PORTARIA N","AVISO"):
        typ = "edital"
    else:
        typ = "outros"

    if typ == "resultado" and not sub:
        sub = "provisorio"
        if hf("FINAL","DEFINITIV") or hh("RESULTADO FINAL","RESULTADO DEFINITIV","DEFINITIVO"): sub = "final"
        if hf("PROVISORI","PRELIMIN") or hh("PROVISORI","PRELIMINAR"): sub = "provisorio"
        if hf("DEFIC","PCD","PNE") or hh("DEFICIENC"): sub = "deficiencia"
        if hf("AUTODECL","NEGR","RACIAL","COTA","HETERO") or hh("AUTODECLARA","HETEROIDENT"): sub = "autodeclaracao"
        if hf("ISEN") or hh("ISENCAO","ISENTO"): sub = "isencao"
    if typ == "edital" and not sub:
        sub = "outro"
        if hf("ABERTURA") or hh("ABERTURA"): sub = "abertura"
        elif hf("_RET","RET_","RETIF","ALTER") or hh("RETIFICA","ALTERAC"): sub = "alteracao"
        elif hf("BANCA") or hh("BANCA EXAMINADORA"): sub = "banca"
        elif hf("LOCAI","HORARIO") or hh("LOCAIS DE PROVA"): sub = "local"

    hn = 1 if namelist else 0
    hs = 1 if (hn and smatch >= SCORE_MIN) else 0
    hc = 1 if cpf >= CPF_MIN else 0
    return typ, sub, hn, hc, hs

def main():
    # quantas linhas processar
    limit = None
    if len(sys.argv) > 1 and sys.argv[1].lower() not in ("all","todos","tudo"):
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("Uso: python3 11_classify_files.py [N|all]"); sys.exit(2)

    with open(CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # garante coluna 'human' (inicializa 1 nas linhas ja classificadas a mao)
    first_time = "human" not in fieldnames
    if first_time:
        fieldnames.append("human")
        for r in rows:
            r["human"] = "1" if (r.get("type") or "").strip() else "0"
        print(f"Coluna 'human' criada: {sum(r['human']=='1' for r in rows)} linhas marcadas "
              f"human=1 (suas classificacoes manuais).")

    scope = rows if limit is None else rows[:limit]
    classified = skipped_human = no_txt = 0
    for r in scope:
        if r.get("human","0") == "1":
            skipped_human += 1
            continue
        rel = r["caminho_rel"]
        p = txt_path(rel)
        if p:
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                text = ""
        else:
            text = ""
        if not text.strip():
            # sem txt (zip, online-only, vazio): so tenta tipo pelo nome; dummies em branco
            typ, sub, hn, hc, hs = analyze(r["arquivo"], "")
            r["type"], r["subtype"] = typ, sub
            r["has_names"] = r["has_cpf"] = r["has_scores"] = ""
            note = (r.get("notes") or "")
            if "sem_txt" not in note:
                r["notes"] = (note + ("; " if note else "") + "sem_txt").strip("; ")
            r["human"] = "0"; no_txt += 1; classified += 1
            continue
        typ, sub, hn, hc, hs = analyze(r["arquivo"], text)
        r["type"], r["subtype"] = typ, sub
        r["has_names"], r["has_cpf"], r["has_scores"] = str(hn), str(hc), str(hs)
        r["human"] = "0"
        classified += 1

    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in fieldnames})

    print(f"Escopo: {'TODAS' if limit is None else 'primeiras '+str(limit)} linhas ({len(scope)}).")
    print(f"  classificadas pelo codigo : {classified}  (das quais {no_txt} sem txt -> so tipo)")
    print(f"  puladas (human=1)         : {skipped_human}")
    print(f"CSV atualizado: {CSV}")

if __name__ == "__main__":
    main()
