# Strategia di test

Rischi principali: (1) **dati** sporchi (HTML Parsoid, redirect, pagine vuote); (2) **qualita' della ricerca**; (3) **robustezza** dell'interfaccia
e della comunicazione con Elasticsearch. La strategia e' una piramide: test veloci senza server alla base, test su Elasticsearch reale sopra.

| Livello | File | Richiede ES | Cosa verifica |
|---|---|---|---|
| Unitari (dati) | `tests/test_parsing.py` | no | pulizia HTML, date, categorie, scarto di record non validi, lettura di tar.gz / gz / NDJSON, righe corrotte |
| Unitari (query DSL) | `tests/test_es_dsl.py` | no | forma della query (`simple_query_string`, boost del titolo, filtri `term`, ordinamento, offset di paginazione, limite di 10.000), parsing della risposta, snippet di riserva con escape, definizione di analizzatore e mapping |
| Sistema (web) | `tests/test_web_offline.py` | no | pagine, API, 404, parametri non validi, XSS, errori chiari se ES e' spento o manca l'indice, con un **client ES finto** (`tests/fakes.py`) |
| Integrazione | `tests/test_es_integration.py` | **si** | indicizzazione (conteggio, ricostruzione, `--limit`), output dell'analizzatore (`_analyze`), stemming, elisione, accenti, stopword, boost del titolo, frasi, esclusioni, trattini, filtri, faccette, paginazione, query malformate, highlighting con escape |
| Qualita' del ranking | `test_es_integration.py::test_gold_set_metrics` + `relevance_queries.json` | **si** | gold set di query con documento atteso: **Precision@1 >= 0.8** e **MRR >= 0.9** |
| Sistema end-to-end | `test_es_integration.py::test_web_*` | **si** | app Flask + Elasticsearch reale |
| Prestazioni | `test_es_integration.py::test_query_latency_on_small_index` | **si** | latenza p95 < 250 ms |
| CLI | `tests/test_cli.py` | in parte | download (URL `file://`), `index` + `stats` |
| Dump reale | `tests/test_realdump.py` | **si** | con `WIKINEWS_DUMP=data/<file>` indicizza 2000 articoli reali |

## Scelte

* **Client finto per la parte web**: la logica dell'app (parametri, template, API, errori) si controlla in millisecondi e senza Docker.
  Il comportamento *linguistico* di Elasticsearch (stemming, accenti, ranking) si puo' pero' verificare solo con un server vero, per questo esiste il livello di integrazione.
* **Indice di test dedicato**: ogni esecuzione crea un indice con nome casuale e lo cancella alla fine; non tocca l'indice `itwikinews`.
* **Corpus di prova piccolo e controllato** (`tests/sample_data.py`): ogni documento esercita un caso preciso (flessione, accenti, titolo contro corpo, testo con `<script>` escapato).
* **Un solo shard** nei test e nell'app: con piu' shard le statistiche BM25 sono per-shard e il ranking su pochi documenti diventa instabile.
* **Soglie del gold set**: se cambiano analizzatore o pesi, il test segnala le regressioni. Un fallimento va investigato senza abbassare le soglie per far passare la suite.
* **Il dump reale non e' nei test automatici** (grande e variabile): si usa lo smoke test opzionale e la checklist manuale.

## Checklist manuale sul dump reale

1. `python -m wikinews_search index` termina senza errori; `python -m wikinews_search stats` mostra un numero plausibile.
2. `WIKINEWS_DUMP=data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz python -m pytest -m realdump`
3. Aprire un articolo da `/article/<id>`: niente markup, numeri di nota o menu.
4. Query di controllo: parola flessa (`elezione`/`elezioni`), accento, frase tra virgolette, filtro per categoria e anno, ordinamento per data.
5. Confrontare 3-4 risultati con la ricerca di it.wikinews.org.

## Esecuzione

```bash
docker compose up -d
python -m pytest                        # tutto
python -m pytest -m "not elasticsearch" # solo test senza server
python -m pytest --cov=wikinews_search
```

## Consolidamento e collegamento alle slide

Le scelte restano Python/Elasticsearch/Flask, BM25, tokenizer e filtri italiani esistenti, un nodo, uno shard primario,
zero repliche. Le correzioni si collegano ai concetti elencati nella traccia delle slide *Lucene & Elasticsearch 2026*;
il file originale delle slide non e' incluso nel repository e non e' stato verificato pagina per pagina.

| Problema riproducibile | Correzione e test | Concetto del corso |
|---|---|---|
| JSON valido ma non oggetto, campi di tipo errato e namespace numerico non zero | Scarto classificato, test in `test_consolidation.py` | Modellazione e qualita' dei documenti prima dell'inverted index |
| Record reale 44564, Lua: soft redirect classificato genericamente come testo breve | Riconoscimento `#softredirect` nell'HTML, motivo esplicito; test anche su variante sintetica lunga | Separazione estrazione/indicizzazione |
| Record reale 49166: citazione su Leopoldo II in una tabella; 48882: didascalia dell'ospedale | Tabelle di contenuto e didascalie preservate; rimozione di classi note di tabelle di servizio | Il testo estratto determina i termini dell'indice |
| `"Roma -Milano"` veniva spezzata dalla regex delle esclusioni | Scansione che rispetta virgolette, escape e gruppi; test unitari e Lucene | Phrase query e operatori booleani |
| Totale oltre 10.000 e parita' di score/data | Numero di pagine limitato e spareggio `article_id` keyword; test con 10.003 documenti | Query DSL, doc values dei keyword, limite di from/size |
| Mancavano conteggi di scarti/errori/documenti finali | Contatori streaming, esiti per operazione bulk e count dopo refresh | Bulk API e ID stabili |
| Un URL `javascript:` in un documento produceva un link attivo anche con escaping HTML | Link alla fonte ammesso solo con schema HTTP/HTTPS valido; regressioni Web | Escaping e validazione dei dati all'interfaccia |
| Su Windows `download --force` non sostituiva un file esistente con `rename` | `Path.replace`, test con URL locale e destinazione preesistente | Riproducibilita' del caricamento dei dati |

Non si interpreta `redirects` come flag: sono pagine che rimandano all'articolo
([schema Wikimedia](https://www.mediawiki.org/wiki/Wikimedia_Enterprise/Documentation)).
Il dump reale contiene molti metadati opzionali: non si inventano date mancanti o categorie.
La pulizia HTML resta euristica: ispezionare ancora un campione di pagine sportive, elettorali, tabelle e citazioni.

## Protocollo sperimentale sul corpus reale

Il test di ranking preesistente (11 documenti sintetici, P@1 e MRR) resta una regressione;
non misura la qualita' delle 12 mila pagine reali. Il confronto reale usa:

| Configurazione | Analyzer di title/body, in indicizzazione e ricerca | Campi | Ranking |
|---|---|---|---|
| A | standard | title, body | BM25 predefinito |
| B | italiano personalizzato esistente | title, body | BM25 predefinito |
| C | italiano personalizzato esistente | title^3, body | BM25 predefinito |

B e C interrogano lo stesso indice: cambia solo il peso del titolo. A e B derivano dal medesimo dump e parser.
Gli indici hanno nomi fissi separati da `itwikinews`, nessun esperimento lo cancella.
`prepare` ricrea gli indici sperimentali: completare un esperimento prima di prepararne un altro.
SHA256 del dump, versione Python/Elasticsearch, UUID degli indici, conteggi, tempi e dimensione primaria sono nel manifest.
Una modifica dell'UUID tra prepare e pool viene rifiutata; tenere gli indici immutati durante il confronto.

`experiments/queries.json` contiene 27 query iniziali con intento esplicito: nomi, eventi, generiche, flessioni,
accenti, frasi e ambiguita'. Sono proposte da rivedere prima della raccolta dei giudizi, non query gia' validate come rilevanti.
Congelare query e intenti prima di confrontare le configurazioni; conservare anche query senza risposte rilevanti,
segnalandole nel rapporto. Le coppie di flessioni sono intenzionali e correlate, quindi le medie non sono campioni indipendenti.

```bash
python -m wikinews_search.evaluation prepare --dump data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --out data/experiment-real
python -m wikinews_search.evaluation pool --out data/experiment-real --repeats 5
```

Il pool e' l'unione dei primi 10 documenti di A/B/C per ciascuna query, deduplicata per ID.
`candidates.jsonl` contiene titolo, testo completo e URL in ordine indipendente da rango e configurazione.
`runs.json` conserva query, graduatorie e latenze; `qrels-template.csv` ha giudizi vuoti.
Un risultato recuperato e' solo un candidato, mai una prova di rilevanza.

1. Copiare `qrels-template.csv` in `qrels.csv`, lasciando invariati query_id e document_id.
2. Un valutatore legge intento e documento completo, confrontandolo con l'originale quando necessario,
   senza consultare `runs.json`. Assegna 0 (non rilevante), 1 (parzialmente rilevante), 2 (direttamente rilevante).
   Compila `assessor` con un identificatore e `note` per motivare i casi ambigui.
3. Far giudicare indipendentemente almeno un sottoinsieme a un secondo studente; discutere i disaccordi,
   conservando le versioni originali e un file finale concordato. Non usare ranking o punteggio per decidere il grado.
4. Giudicare tutti i candidati: il calcolo rifiuta righe vuote, duplicate, estranee e giudizi mancanti.
   Versionare query, qrels e manifest, insieme ai run e al rapporto (la cartella data e' ignorata da Git).
   Per condividere i testi rispettare le licenze degli articoli originali.

```bash
python -m wikinews_search.evaluation evaluate --out data/experiment-real --qrels data/experiment-real/qrels.csv
```

Il comando scrive `metrics.json` con valori per query e medie macro:

* **Precision@5**: numero di documenti con grado > 0 nei primi 5 diviso 5; posizioni mancanti valgono zero.
* **MRR@10**: reciproco del rango del primo documento con grado > 0, zero se assente entro 10.
  E' una MRR troncata, dato che il run recupera 10 risultati.
* **nDCG@10**: DCG con guadagno `2^grado - 1` e sconto `log2(rango+1)`, normalizzata rispetto ai migliori
  10 giudizi del pool. Zero se non ci sono rilevanti nel pool. L'ideale e' limitato al pool, non all'intero dump.
* **Latenza p50/p95**: nearest-rank sui tempi client in millisecondi (rete e deserializzazione incluse),
  un warm-up escluso per query/configurazione e cinque ripetizioni misurate, ordine A/B/C ruotato.
  Si conserva lo stesso percorso DSL dell'app, incluse aggregazioni e highlighting; l'esportazione richiede il corpo completo.
* **Indicizzazione e dimensione**: tempo totale per indice (lettura/parsing, creazione, bulk, refresh e conteggio),
  store primario dopo flush, senza force merge. B e C condividono questi costi.

Confrontare B-A per l'analyzer e C-B per il boost. Riportare anche differenze per query, query senza rilevanti,
hardware, carico, versioni e dimensione del corpus. Cache calda e ordine di costruzione degli indici influenzano i tempi:
non attribuire differenze minime a un miglioramento generale. Non si calcolano recall o significativita' statistica.
Il pooling puo' perdere rilevanti non recuperati da nessuna configurazione; una nuova configurazione richiede nuovo pooling
e nuovi giudizi. Nessuna metrica di qualita' reale e' disponibile finche' non si completa il lavoro umano.

## Comandi Windows per il dump reale

```powershell
python -m wikinews_search validate-dump --dump data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --report data/validation.json
$env:WIKINEWS_DUMP = 'data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz'
python -m pytest -m realdump
```

Il test realdump esistente e' uno smoke test sui primi 2.000 articoli validi; `validate-dump` legge invece tutto il dump.
Il caricamento completo dei due indici sperimentali verifica anche mapping, Bulk API e conteggio finale sul corpus reale.
I contatori distinguono operazioni riuscite e documenti unici: `_id` stabile rende gli aggiornamenti idempotenti senza
caricare tutti gli identificatori in memoria. Le righe bianche non sono record; JSON o UTF-8 malformati sono scarti.
Le eccezioni di trasporto o archivio interrompono l'esecuzione: un report parziale non prova un caricamento completo.

I risultati effettivamente ottenuti e i limiti della prima esecuzione sono in [experiments/RESULTS.md](experiments/RESULTS.md),
con manifest e run versionati. I giudizi reali restano da completare.
