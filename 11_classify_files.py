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

QUALIDADE (validado contra 3 concursos-gold, 124 arquivos, + auditoria manual das
300 primeiras linhas)
    has_cpf ~100%   has_scores ~99%   has_names ~98%   type ~91%   subtype ~61%
    Sinal central: barras "/" por KB e numeros de inscricao dizem se e' lista de
    candidatos. type/subtype ainda tem erros -> revise e va marcando human=1 no que
    corrigir; quanto mais voce corrigir, melhor da pra afinar as regras depois.
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
INSCR = re.compile(r'\b\d{6,9}\b')                                 # numero de inscricao (candidatos)
ABCDE = re.compile(r'(?:\b[A-E]\b[ \t]+){5,}')                     # linha de gabarito: A B C D E ...

# limiares calibrados contra 3 concursos-gold + auditoria manual das 300 primeiras linhas
SLASH_PER_KB = 10     # barras "/" por KB: listas de candidatos usam " / " entre registros
INSCR_MIN    = 30     # nº de numeros de inscricao (6-9 digitos) p/ ser "lista de candidatos"
SCORE_MIN    = 60     # nº de notas p/ has_scores (so vale se ja for lista)
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
    """Retorna (type, subtype, has_names, has_cpf, has_scores).

    Regra central (validada com a auditoria do usuario): o numero de barras por KB
    e a quantidade de numeros de inscricao dizem se o arquivo e' uma LISTA DE
    CANDIDATOS (resultado/inscricao). Poucas barras => NAO e' resultado. Alem disso,
    'codigos' de texto identificam o tipo: 'torna publico/publica' => edital;
    'em razao de erro material' => edital/alteracao; 'sera aplicada no dia'/'duracao
    de' => edital/local; 'modelo de formulario'/'a banca examinadora' => outros.
    """
    F = norm(fname); n = len(text) or 1
    title = norm(text[:800])            # titulo do documento (primeiros ~800 chars)
    head  = norm(text[:8000])           # cabecalho maior p/ 'codigos' de texto
    body  = text[:2_000_000]
    slash_kb = text.count("/") / (n / 1000.0)
    insc  = len(INSCR.findall(body))
    smatch = len(SCORE.findall(body))
    cpf    = len(CPF.findall(text)) + len(CPFM.findall(text))
    abcde  = bool(ABCDE.search(text[:20000]))
    is_list = slash_kb >= SLASH_PER_KB or insc >= INSCR_MIN

    def hf(*k): return any(x in F for x in k)       # no nome do arquivo
    def ht(*k): return any(x in title for x in k)   # no titulo
    def hh(*k): return any(x in head for x in k)    # no cabecalho

    typ, sub = "outros", ""
    # 1) gabarito / padrao de resposta / espelho
    if hf("GABARIT","GAB_","PADRAO_DE_RESPOSTA","PADRAORESPOSTA","ESPELHO") \
       or ht("PADRAO DE RESPOSTA","GABARITO OFICIAL","ESPELHO DE PROVA") \
       or (hh("GABARITO") and abcde) or ("JUSTIFICATIV" in F and "GABARITO" in head):
        typ = "gabarito"
        sub = "discursiva" if hf("DISC","REDACAO","PECA","DISSERT") \
              or ht("PADRAO DE RESPOSTA","DISCURSIV","PECA","QUESTAO","DISSERTA") else "objetiva"
        if hf("JUSTIFICATIV") or ht("JUSTIFICATIVAS DE ALTERAC","ALTERACAO DO GABARITO"): sub = "alteracao"
    # 2) outros por 'codigo' (formulario, requerimento, capa de recurso, banca)  -- antes de edital
    elif hh("MODELO DE FORMULARIO","A BANCA EXAMINADORA") \
         or hf("CAPA_DE_RECURSO","REQUERIMENTO","FORMULARIO","MODELO"):
        typ = "outros"
    # 3) candidato x vaga
    elif hf("DEMANDA") or ht("CANDIDATOS POR VAGA","DEMANDA DE CANDIDATOS"):
        typ = "candidatovaga"
    # 4) LISTA de candidatos -> resultado (ou inscricao)  -- muitas barras / nº de inscricao
    elif is_list:
        if hf("_INSC","RES_PROV_INSC","RES_FINAL_INSC","REL_FINAL_INSC","REL_PROV_INSC") and smatch < SCORE_MIN:
            typ = "inscricao"; sub = "final" if hf("FINAL") else "provisorio"
        else:
            typ = "resultado"; sub = "provisorio"
            if hf("FINAL") or ht("RESULTADO FINAL","RELACAO FINAL"): sub = "final"
            if hf("PROV") or ht("PROVISORI","RELACAO PROVISORIA"): sub = "provisorio"
            # subtipos por sufixo do nome do arquivo (regras do usuario)
            if hf("_AE","_PCD","DEFIC"): sub = "deficiencia"
            if hf("COTAS","NEGR","RACIAL","AUTODECL","HETERO"): sub = "autodeclaracao"
            if hf("ISEN"): sub = "isencao"
    # 5) edital por 'codigo' de texto / nome  -- so chega aqui se NAO for lista
    elif hh("TORNA PUBLIC") or ht("EDITAL N","EDITAL No","EDITAL Nº") \
         or hf("ED_","EDITAL","EXTRATO","COMUNICADO","AVISO","PORTARIA") \
         or ht("COMUNICADO","AVISO","PORTARIA"):
        typ = "edital"; sub = "outro"
        if hf("ABERTURA") or ht("ABERTURA"): sub = "abertura"
        elif hf("RETIF","_RET","ALTER") or hh("EM RAZAO DE ERRO MATERIAL","RETIFICA","ALTERAC"): sub = "alteracao"
        elif hf("BANCA") or ht("BANCA EXAMINADORA"): sub = "banca"
        elif hf("LOCAI","LOCAL","HORARIO") or hh("SERA APLICADA NO DIA","DURACAO DE"): sub = "local"
    # 6) prova (caderno) -- por ultimo: 'prova objetiva' aparece citada em editais/resultados
    elif ht("PROVA OBJETIVA","PROVA DISCURSIVA","PROVA ESCRITA","PROVA SUBJETIVA","PROVAS SUBJETIVAS") \
         or re.search(r'_\d{2,3}_(0\d|DISC|P\d)\b', F) or F.endswith("_DISC") \
         or ht("MARQUE, PARA CADA","ITENS A SEGUIR","FOLHA DE RESPOSTAS"):
        typ = "prova"
        sub = "discursiva" if hf("DISC","REDACAO","_P2","_P3","_P4") \
              or ht("DISCURSIV","SUBJETIV","REDACAO") else "objetiva"

    hn = 1 if is_list else 0
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

    def save():
        with open(CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in fieldnames})

    scope = rows if limit is None else rows[:limit]
    todo = sum(1 for r in scope if r.get("human","0") != "1")   # quantas serao classificadas
    print(f"Escopo: {'TODAS' if limit is None else 'primeiras '+str(limit)} linhas "
          f"({len(scope)}); a classificar: {todo}. (checkpoint a cada 5000)")
    CHECKPOINT = 5000
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
        else:
            typ, sub, hn, hc, hs = analyze(r["arquivo"], text)
            r["type"], r["subtype"] = typ, sub
            r["has_names"], r["has_cpf"], r["has_scores"] = str(hn), str(hc), str(hs)
            r["human"] = "0"
            classified += 1
        if classified % 500 == 0:
            print(f"  ... {classified}/{todo} classificadas", flush=True)
        if classified % CHECKPOINT == 0:
            save()   # checkpoint: nao perde progresso se interromper

    save()

    print(f"Escopo: {'TODAS' if limit is None else 'primeiras '+str(limit)} linhas ({len(scope)}).")
    print(f"  classificadas pelo codigo : {classified}  (das quais {no_txt} sem txt -> so tipo)")
    print(f"  puladas (human=1)         : {skipped_human}")
    print(f"CSV atualizado: {CSV}")

if __name__ == "__main__":
    main()
