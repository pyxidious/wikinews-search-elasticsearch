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
* **Soglie del gold set**: se cambiano analizzatore o pesi, il test segnala le regressioni. Alla prima esecuzione su un server reale conviene controllare i valori effettivi e, se serve, tarare le soglie.
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
