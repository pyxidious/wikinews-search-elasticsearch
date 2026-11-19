# Protocollo di annotazione — riferimento **LLM-only** (non human-validated)

**Natura:** 244 giudizi generati mediante una sessione di GPT-6 su 18 query e relativi documenti del pool top-10 A/B/C. **Non costituisce una ground truth umana, certificata o indipendente dai modelli linguistici.**

## Fonti e cecità

- Input: `results.zip/blind_candidates.jsonl` e `validation_queries.json` del benchmark Codex.
- I 244 candidati sono stati valutati per intento informativo usando titolo e testo disponibile; per alcune notizie lunghe è stata effettuata una lettura mirata dei passaggi pertinenti.
- La decisione sulle etichette è stata presa senza usare l'ordine dei risultati, le configurazioni A/B/C o le precedenti classificazioni AI. Il mapping privato degli ID è stato usato **dopo** le etichette, esclusivamente per associare i giudizi alle graduatorie.
- Fonte delle etichette: `GPT-6-LLM-only`, una sola passata. Nessun partecipante umano ha eseguito o convalidato questi giudizi. Le successive analisi sono condizionate alla correttezza delle etichette.
- Dataset delle query: costruito deliberatamente da Codex prima dei ranking, non un campione casuale di query degli utenti. Articoli Wikinews dal dump ufficiale 2025-03-20.

## Rubrica fissata

- **0 = non rilevante**: il documento non soddisfa il bisogno esplicitato nell'intento; una coincidenza lessicale non basta. Sono esclusi eventi di altro paese/periodo se l'intento specifica un evento preciso.
- **1 = rilevanza parziale**: l'intento è discusso come componente secondaria o in un contesto più ampio, ma non è il tema principale dell'articolo.
- **2 = direttamente rilevante**: l'argomento principale soddisfa chiaramente l'intento; non giudicare veridicità giornalistica o autorevolezza delle fonti, ma pertinenza alla query.
- Le coppie di query morfologiche e accentuali hanno gli stessi intenti: le etichette per gli articoli comuni sono controllate per coerenza.

## Metodologia statistica

- Analisi sulle graduatorie congelate `ranking_private.json` (presenti in `results.zip`), con funzione `analyze` dello script originale `ranking_analysis.py`.
- **Non** è stata invocata l'opzione `--human-confirmed` dello script originale e non è stato fabbricato un secondo valutatore.
- nDCG@10 primaria, Precision@5 e MRR@10 secondarie. Il valore ideale di nDCG è calcolato sui candidati nel pool, non sull'intero corpus.
- Bootstrap percentile 95%, 10.000 ricampionamenti per gruppi di query come nello script Codex. Gli intervalli riflettono **solo la variabilità dei gruppi di query**, non l'errore di annotazione dell'LLM o lo spostamento a query reali di utenti.
- Sensibilità: rietichettatura pessimistica (tutti i gradi 1 → 0), ottimistica (tutti 1 → 2), esclusione della query Brexit v05 e del gruppo accenti v12/v13.

## Risultato preliminare

| Metrica | A Standard | B Italiano | C Italiano + boost titolo×3 |
|---|---:|---:|---:|
| nDCG@10 | 0,8828 | 0,9607 | 0,8926 |
| Precision@5 | 0,8222 | 0,8778 | 0,8778 |
| MRR@10 | 0,9722 | 1,0000 | 0,9444 |

- Differenza nDCG B−A: **+0,0779** [IC95 +0,0088; +0,1510].
- Differenza nDCG C−B: **−0,0681** [IC95 −0,1953; −0,0001].
- Il risultato C−B è fortemente influenzato dalla query Brexit v05: senza v05 diventa **−0,0133**. Non interpretare il secondo IC come prova robusta di inferiorità generale del boost.
- L'effetto dell'analyzer italiano B−A dipende anche dai test sugli accenti: senza le query v12/v13 si riduce a **+0,0444**.

## Limiti e cosa NON rivendicare

1. Non è verificata la correttezza delle 244 etichette da esseri umani o da un secondo modello indipendente.
2. Non è calcolabile l'accordo fra valutatori (kappa) con una singola annotazione.
3. Le classificazioni possono riflettere bias semantici eccessivamente permissivi, soprattutto su intenti generici.
4. Bootstrap sulle query e IC95 **non** rendono le etichette una verità di riferimento verificata.
5. Il pool top-10 può perdere altri documenti rilevanti; non calcolare recall globale.
6. Gli intenti e le query sono progettati, non un campione probabilistico di query reali.
7. L'interpretazione dei risultati non costituisce prova universale di miglioramento.

## Replicare le metriche (non la generazione semantica delle etichette)

Dalla directory di questo pacchetto:

```bash
python recompute_ai_only.py --archive /percorso/results.zip --qrels qrels_llm_only.csv --out recomputed
```

Per migliorare la robustezza senza valutatori umani, effettuare una **seconda annotazione cieca con un modello diverso** a partire dagli stessi candidati, senza fornire al secondo modello questi giudizi. Confrontare etichette, accordo e metriche per modello; eventualmente arbitrare i disaccordi con un terzo modello, dichiarandolo come protocollo AI-only. Non usare l'etichetta `human-confirmed`.
