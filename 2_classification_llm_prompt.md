# LLM Prompt for CEBRASPE 2006 Document Classification

Use this prompt with rows from:

`Data/CEBRASPE/Intermediate/classification_2006/classification_2006_for_llm_review.csv`

Prompt:

```text
You are classifying a text-extracted PDF from the old CESPE/CEBRASPE concurso archive.

Return JSON only. Choose exactly one `doc_type` from:

- opening_notice
- final_result
- provisional_result
- intermediate_result
- convocation
- locations
- demand
- answer_key
- exam
- erratum
- appeals
- communication
- manual_or_regulation
- administrative
- other

Definitions:

- opening_notice: edital de abertura or main rules, positions, vacancies, pay, registrations.
- final_result: final candidate result for a concurso or major stage, usually with grades/classification.
- provisional_result: provisional candidate result, usually subject to appeal.
- intermediate_result: result of one phase/stage, e.g. titles, oral, medical exam, physical test, investigation.
- convocation: calls candidates to a phase, course, exam, matrícula, appointment, or next step.
- locations: locations/times of exams or other events.
- demand: demanda de candidatos por vaga or inscritos/vagas table.
- answer_key: gabarito preliminar/definitivo or gabarito-change justifications.
- exam: prova/caderno de questões.
- erratum: retificação, errata, sub judice, judicial correction, suspension, cancellation.
- appeals: recurso forms, appeal instructions, or appeal-result access notices.
- communication: short comunicado/aviso/nota that does not fit above.
- manual_or_regulation: manual, regulation, resolution, instruction, form annex with rules.
- administrative: ata, despacho, publication, appointment/naming record, administrative artifact.
- other: none of the above or insufficient text.

Input:
filename: {filename}
rule_label: {doc_type_rule}
rule_evidence: {evidence}
head_snippet: {head_snippet}
candidate_snippet: {candidate_snippet}

Return:
{
  "doc_type": "...",
  "confidence": 0.0,
  "is_candidate_result": true,
  "result_stage": "final|provisional|intermediate|not_applicable|unknown",
  "has_candidate_rows": true,
  "reason": "short explanation"
}
```

