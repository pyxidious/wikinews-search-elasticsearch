# Confronto indipendente AI-only — GPT-6 e Claude Opus 5.5

**Natura del riferimento:** due serie di annotazioni LLM cieche; nessuna valutazione o conferma umana. Non è una ground truth umana.

- Coppie validate: **244**, query **18**, gruppi **15**.
- Sono state confrontate le stesse 244 coppie tramite ID opachi; nessun documento mancante o duplicato.

## Concordanza sulle etichette

- Accordo esatto: **78.28%** (191/244), IC95 bootstrap per gruppi [66.44%; 89.88%].
- Kappa pesato quadratico: **0.8016**; IC95 [0.5634; 0.9349].
- Kappa pesato lineare: **0.7205**.
- Accordo binario rilevante/non rilevante (1/2 vs 0): **94.26%**; IC95 [88.85%; 100.00%].
- Disaccordi: **53**, di cui 4 di due livelli.
- Matrice di confusione (righe GPT-6, colonne Claude; classi 0,1,2):

| GPT-6 \ Claude | 0 | 1 | 2 |
|---|---:|---:|---:|
| 0 | 45 | 0 | 0 |
| 1 | 10 | 25 | 2 |
| 2 | 4 | 37 | 121 |

## Metriche del ranking basate sulle etichette di ciascun giudice

| Giudice | Metrica | A | B | C | B−A | C−B |
|---|---|---:|---:|---:|---:|---:|
| GPT-6 | nDCG@10 | 0.8828 | 0.9607 | 0.8926 | 0.0779 | -0.0681 |
| Claude-Opus-5.5 | nDCG@10 | 0.8193 | 0.8916 | 0.8194 | 0.0723 | -0.0723 |
| GPT-6 | P@5 | 0.8222 | 0.8778 | 0.8778 | 0.0556 | -0.0000 |
| Claude-Opus-5.5 | P@5 | 0.8000 | 0.8778 | 0.8556 | 0.0778 | -0.0222 |
| GPT-6 | MRR@10 | 0.9722 | 1.0000 | 0.9444 | 0.0278 | -0.0556 |
| Claude-Opus-5.5 | MRR@10 | 0.9722 | 1.0000 | 0.9444 | 0.0278 | -0.0556 |

**Metrica primaria:** nDCG@10. P@5 e MRR@10 sono secondarie; nDCG usa IDCG limitato al pool A/B/C top-10, non il corpus intero.

### Confronti appaiati per nDCG@10

| Giudice | Contrasto | Differenza media | IC 95% bootstrap per gruppi | Vittorie/pari/sconfitte |
|---|---|---:|---|---|
| GPT-6 | B-A | 0.0779 | [0.0088; 0.1510] | 8/7/3 |
| Claude-Opus-5.5 | B-A | 0.0723 | [0.0213; 0.1329] | 10/5/3 |
| GPT-6 | C-B | -0.0681 | [-0.1953; -0.0001] | 4/7/7 |
| Claude-Opus-5.5 | C-B | -0.0723 | [-0.2054; 0.0038] | 4/6/8 |

### Analisi di sensibilità per nDCG@10

| Giudice | Contrasto | Tutte | Senza Brexit v05 | Senza accenti v12/v13 |
|---|---|---:|---:|---:|
| GPT-6 | B-A | 0.0779 | 0.0825 | 0.0444 |
| GPT-6 | C-B | -0.0681 | -0.0133 | -0.0696 |
| Claude-Opus-5.5 | B-A | 0.0723 | 0.0766 | 0.0436 |
| Claude-Opus-5.5 | C-B | -0.0723 | -0.0177 | -0.0735 |

## Dove i due LLM dissentono di più

| Query | Descrizione | Discordanti / totale |
|---|---|---:|
| v10 | studente | 11/17 |
| v18 | borsa | 9/14 |
| v11 | studenti | 7/14 |
| v16 | calcio | 6/15 |
| v07 | cambiamento climatico | 4/17 |
| v08 | lavoratore | 4/19 |
| v01 | Giorgio Napolitano | 3/11 |

Controllo di coerenza sui documenti ripetuti nelle coppie flessive/accentuali: **0** contraddizioni interne.

## Interpretazione e limiti

- Le due annotazioni sono state assegnate a modelli differenti e non sono state fornite a Claude le etichette GPT-6; il confronto è AI-only.
- Claude ha dichiarato una lettura selettiva dei documenti molto lunghi (introduzione e passaggi pertinenti), non integrale: possibile limite delle annotazioni.
- I due modelli non coincidono perfettamente nel criterio 1 vs 2; una media dei due gradi non sarebbe una adjudication indipendente.
- Gli IC sono bootstrap per 15 gruppi di query, non incorporano errori sistematici dei modelli o differenze nella lettura.
- Query e intenti sintetici non sono campionati da log utenti; l’accordo AI non prova la correttezza rispetto a un giudice umano.
- Il benchmark usa un pool top-10 e non può stimare recall dell’intero corpus.
- Le metriche vanno presentate separatamente per giudice; non usare --human-confirmed.

## Provenienza e riproducibilità

- GPT-6 qrels SHA256: `3be1358b9bea74270286e1a30beb404ead497f6adac24093ecc3e099ed317452`
- Claude qrels SHA256: `8001cd894c92cd34b4ed550fd7a92152f95397b5f5fe92a61e66c7ac808c344b`
- Bootstrap: 10000 ricampionamenti appaiati con seed 20261118; unità di ricampionamento: gruppo di query.
- Fonte ranking congelati: `results.zip/ranking_private.json`; nessun indice è stato ricalcolato.
- I CSV e lo script `compare_llm_judges.py` sono conservati insieme al rapporto.
