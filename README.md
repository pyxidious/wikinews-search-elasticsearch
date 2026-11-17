# Wikinotizie Search (versione Elasticsearch)

Motore di ricerca con interfaccia web per le notizie in italiano di [it.wikinews.org](https://it.wikinews.org/),
costruito a partire dal dump Wikimedia Enterprise HTML del 20 marzo 2025
([itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz](https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz)).
Homework 4 del corso di Ingegneria dei Dati.

Questa versione usa **Elasticsearch 8** (basato su Lucene).

## Funzionalita'

* Ricerca full-text su titolo e testo con un **analizzatore italiano personalizzato**: tokenizer standard, elisione (`l'`, `dell'`...),
  minuscole, stopword italiane, rimozione degli accenti, stemmer `light_italian`. `elezione` trova `elezioni`, `citta` trova `città`,
  `Italia` trova `L'Italia`.
* Ranking **BM25** con titolo pesato 3x (`title^3`).
* Sintassi (`simple_query_string`, non genera mai errori di sintassi): `"frase esatta"`, `+obbligatorio`, `-escluso`, `a | b`, `prefisso*`, `parola~1`.
* Frammenti con parole evidenziate (highlighting di Elasticsearch, con escape dell'HTML), **filtri a faccette** (categoria, anno)
  calcolati con le *aggregations*, ordinamento per rilevanza o data, paginazione.
* Pagina di lettura dell'articolo e **API JSON** (`/api/search`).

## Architettura

```
dump .tar.gz --(dump.py, streaming)--> record JSON --(parsing.py)--> Article --(indexer.py, bulk API)--> Elasticsearch
                                                                                                              |
browser --> Flask (webapp.py) --> searcher.py (query DSL, aggregations, highlight) <--------------------------+
```

| Modulo | Ruolo |
|---|---|
| `dump.py` | legge il dump in streaming (tar.gz, gz o NDJSON); salta le righe corrotte |
| `parsing.py` | HTML -> testo pulito, categorie, data; scarta namespace diversi da 0, redirect e pagine vuote |
| `indexer.py` | settings (analizzatore `italiano`), mapping, creazione dell'indice e caricamento con `helpers.bulk` |
| `searcher.py` | costruisce la query (`build_body`), la esegue e traduce la risposta (`parse_response`) |
| `webapp.py` | pagine web e API |
| `cli.py` | comandi `download`, `index`, `serve`, `stats` |

Mapping: `title` e `body` come `text` con analizzatore `italiano`; `category` e `year` come `keyword` (filtri e faccette); `date` come `date`;
un solo shard e nessuna replica, cosi' le statistiche BM25 sono coerenti anche su un nodo singolo.

## Installazione

Richiede Python 3.10+ e Docker (per Elasticsearch).

```bash
git clone <URL-DEL-TUO-REPOSITORY>
cd wikinews-search-elasticsearch
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d          # avvia Elasticsearch 8.15 su http://localhost:9200 (attendere ~30 s)
curl http://localhost:9200    # deve rispondere con un JSON
```

Il `docker-compose.yml` disattiva la sicurezza di Elasticsearch: va bene in locale, **non in produzione**.

## Uso

```bash
python -m wikinews_search download     # scarica il dump in data/
python -m wikinews_search index        # crea l'indice "itwikinews" e carica gli articoli
python -m wikinews_search serve        # avvia http://127.0.0.1:5000
```

Per provare il sistema subito, senza scaricare il dump, con 11 notizie d'esempio:

```bash
python scripts/make_sample_dump.py data/sample.json.tar.gz
python -m wikinews_search index --dump data/sample.json.tar.gz
python -m wikinews_search serve
```

Opzioni: `--es-url` (o variabile `ES_URL`, default `http://localhost:9200`), `--index-name` (o `ES_INDEX`, default `itwikinews`),
`index --limit 500`, `serve --host --port`. Per un cluster con autenticazione: variabili `ES_USERNAME` e `ES_PASSWORD`.
`index` ricrea l'indice da zero a ogni esecuzione. Per un uso in produzione: `pip install gunicorn` e
`gunicorn "wikinews_search.webapp:create_app()"`.

### API

```
GET /api/search?q=terremoto&category=Italia&year=2023&sort=date&page=1&page_size=10
GET /health
```

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest                 # con Elasticsearch attivo (docker compose up -d) esegue tutto
```

Senza Elasticsearch i test di integrazione vengono saltati e restano quelli unitari e web (client finto). La strategia completa e'
in [TESTING.md](TESTING.md). La CI di GitHub Actions avvia un container Elasticsearch ed esegue l'intera suite.

## Note e limiti

* `from + size` e' limitato a 10.000 risultati (`index.max_result_window`); per scorrere oltre servirebbe `search_after`.
* Il formato del dump (`name`, `identifier`, `url`, `namespace`, `date_created`, `categories`, `article_body.html`) segue la documentazione
  Wikimedia Enterprise; la pulizia dell'HTML (`REMOVE_SELECTORS`) e le categorie ignorate (`IGNORED_CATEGORIES`) in `parsing.py` si adattano dopo aver visto i dati reali.
* Miglioramenti possibili: alias dell'indice per ricostruirlo senza interruzioni, suggerimenti di ricerca (`completion suggester`), sicurezza e TLS.

I testi di Wikinotizie sono disponibili con licenza CC BY 2.5.
