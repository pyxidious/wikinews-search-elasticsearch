# Esperimenti: rilevanza, prestazioni e riproducibilità

Gli esperimenti confrontano tre configurazioni: **A**, analyzer standard e BM25 con pesi uniformi;
**B**, analyzer italiano e BM25 con pesi uniformi; **C**, stesso indice di B con peso del titolo `title^3`.
Il confronto B−A riguarda l'analyzer; C−B riguarda il peso del titolo.

## Metodi e risultati

| Tipologia | Metodologia | Risultati e limiti |
|---|---|---|
| [Valutazione della rilevanza AI-only](llm-evaluation/README.md) | 18 query sintetiche, 244 coppie query-documento, 15 gruppi; giudizi GPT-6 e Claude Opus 5.5; nDCG@10 primaria, P@5 e MRR@10 secondarie | B ha la nDCG@10 media più alta per entrambi i giudici nel pool. L'effetto del peso del titolo è sensibile alla query Brexit. Nessuna validazione umana. |
| [Latenza e capacità di ricerca](performance-20261118/README.md) | Elasticsearch diretto e HTTP Flask; carico controllato e ciclo chiuso; 94 query sintetiche, 240 celle, cinque repliche per condizione | 1.336.275 richieste misurate; 113/120 celle di capacità soddisfano il criterio prefissato. Sette falliscono per variabilità; due errori client sono conservati nei dati grezzi. |
| [Indicizzazione](performance-20261118/README.md) | 20 caricamenti, con HTML completo e preprocessato; confronto tra analyzer standard e italiano | 12.257 operazioni e 12.209 documenti unici per caricamento, zero errori Bulk. Durata, documenti/s e store sono ricalcolabili dalle misure originali. |
| [Verifica del dump e confronto esplorativo A/B/C](RESULTS.md) | 27 query diagnostiche, pool di 354 coppie da giudicare; cinque ripetizioni dopo warm-up per query e configurazione | Conteggi del corpus, dimensioni degli indici e latenze locali con cache calda. Nessuna metrica di rilevanza sul pool esplorativo; i tempi di costruzione non isolano il costo dell'analyzer. |

Il [rapporto di verifica scientifica](llm-evaluation/FINAL_REPORT.md) presenta metriche, contrasti,
intervalli e sensibilità. Le query sono sintetiche e il corpus è storico: questi risultati non dimostrano
validità generale per utenti reali. L'accordo fra LLM non certifica la correttezza delle etichette.

## Verificare e riprodurre i calcoli

- [Rilevanza: ambiente, test di integrità e ricalcolo](llm-evaluation/README.md): verifica dei manifest,
  delle annotazioni e di 345 valori storici, con tolleranze assoluta e relativa 1e-12.
- [Prestazioni: dati grezzi e ricalcolo](performance-20261118/README.md): verifica dell'archivio e dei suoi
  membri, poi confronto con le statistiche originali; tolleranza assoluta 1e-9 e relativa 1e-12.
- [Kit, checksum e distribuzione manuale](RELEASE_ASSETS.md): preparazione locale e uso degli asset.
  L'archivio dei dati grezzi è preparato localmente; il suo URL di download non è ancora assegnato.
- [Strategia di test del progetto](../TESTING.md): distingue controlli offline e test con Elasticsearch.

I comandi di ricalcolo non invocano modelli né interrogano Elasticsearch. Una nuova misura fisica
richiede una campagna separata: ricalcolare le statistiche non significa rieseguire il benchmark.

## Provenienza e documenti conservati

Il dump Wikimedia Enterprise HTML è del **20 marzo 2025**. Il rapporto esplorativo documenta
l'esecuzione del **17 novembre 2026**; la campagna prestazionale è del **18 novembre 2026**;
il rapporto di consolidamento scientifico è del **19 novembre 2026**. Queste date identificano
le sorgenti e le fasi del lavoro, non versioni intercambiabili dello stesso esperimento.

I protocolli, i README e i rapporti inclusi nei manifest restano conservati byte per byte,
insieme ai titoli originali. I nomi dei percorsi datati sono mantenuti per preservare collegamenti,
checksum e comandi di riproduzione. Questo indice offre una lettura per contenuto tecnico senza
riscrivere gli originali. Le date delle annotazioni LLM non sono registrate: i timestamp ZIP
non le sostituiscono; vedere [provenienza dei prompt e dei modelli](llm-evaluation/PROMPT_PROVENANCE.md).
