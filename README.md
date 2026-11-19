# Wikinotizie Search: ricerca full-text con Elasticsearch

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
* Sintassi tollerante agli errori con `simple_query_string`: spazi e `|` indicano OR; `Roma + Milano` indica AND;
  `"banca centrale"` cerca una frase analizzata, `-escluso` esclude un termine, `prefisso*` cerca un prefisso, `parola~1` ammette un errore.
* Frammenti con parole evidenziate (highlighting di Elasticsearch, con escape dell'HTML), **filtri a faccette** (categoria, anno)
  calcolati con le *aggregations*, ordinamento per rilevanza o data, paginazione.
* Pagina di lettura dell'articolo e **API JSON** (`/api/search`).
  Il link alla fonte nella pagina di lettura ammette solo URL HTTP/HTTPS validi.

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
| `indexer.py` | settings (analizzatore `italiano`), mapping, creazione dell'indice e caricamento con `helpers.streaming_bulk` |
| `searcher.py` | costruisce la query (`build_body`), la esegue e traduce la risposta (`parse_response`) |
| `webapp.py` | pagine web e API |
| `cli.py` | comandi `download`, `index`, `serve`, `stats` |

Mapping: `title` e `body` come `text` con analizzatore `italiano`; `category` e `year` come `keyword` (filtri e faccette); `date` come `date`;
un solo shard e nessuna replica, cosi' le statistiche BM25 sono coerenti anche su un nodo singolo.
`article_id` e' un `keyword` che replica l'identificatore stabile usato come `_id`, per spareggiare punteggi e date uguali.
Gli indici creati con la versione precedente devono essere ricostruiti con `index` prima di usare il nuovo ordinamento.

## Installazione

Richiede Python 3.10+ e Docker (per Elasticsearch).

```bash
git clone https://github.com/pyxidious/wikinews-search-elasticsearch.git
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

Se il certificato del server non viene validato dal trust store Python, su Windows si puo' usare il trust store
di sistema tramite `curl.exe` (senza disabilitare la verifica TLS):

```powershell
curl.exe --fail --location --output data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz
```

Per provare il sistema subito, senza scaricare il dump, con 11 notizie d'esempio:

```bash
python scripts/make_sample_dump.py data/sample.json.tar.gz
python -m wikinews_search index --dump data/sample.json.tar.gz
python -m wikinews_search serve
```

Opzioni: `--es-url` (o variabile `ES_URL`, default `http://localhost:9200`), `--index-name` (o `ES_INDEX`, default `itwikinews`),
`index --limit 500` (numero positivo di articoli validi), `index --report data/index-report.json`, `serve --host --port`.
Per autenticazione: variabili `ES_USERNAME` e `ES_PASSWORD`.
`index` ricrea l'indice da zero a ogni esecuzione. Per un uso in produzione: `pip install gunicorn` e
`gunicorn "wikinews_search.webapp:create_app()"`.

### API

```
GET /api/search?q=terremoto&category=Italia&year=2023&sort=date&page=1&page_size=10
GET /health
```

### Sintassi e paginazione

`Roma Milano` equivale a `Roma | Milano`. Per AND scrivere `Roma + Milano`: `+` e' un operatore binario,
non una promessa che `+parola` da sola renda obbligatorio quel termine in ogni espressione OR.
Le virgolette mantengono l'ordine e le posizioni dei token, ma l'analyzer applica ancora stopword, stemming e accenti:
non e' un confronto letterale di stringhe. `Emilia-Romagna` non e' una negazione;
`"Emilia-Romagna"` resta una frase. `elezioni -Roma` e `elezioni -"banca centrale"` applicano esclusioni globali
ai termini autonomi esterni ai gruppi. Nei gruppi vale la sintassi nativa di Lucene; con OR, per un'esclusione obbligatoria
usare `+-`, ad esempio `(elezioni +-Roma)`. Escape con `\` per gli operatori letterali.
Le parti sintatticamente non valide vengono ignorate dal parser; `lenient` riguarda invece gli errori di formato dei campi.
Riferimento: [simple_query_string in Elasticsearch 8.15](https://www.elastic.co/guide/en/elasticsearch/reference/8.15/query-dsl-simple-query-string-query.html).

Il totale e' quello effettivo delle corrispondenze; le pagine navigabili sono limitate a
`min(ceil(total/page_size), floor(10000/page_size))`. Si mostrano solo pagine complete entro la finestra
(fino a `floor(10000/page_size)*page_size` risultati); la pagina finale del corpus puo' naturalmente essere parziale.
Pagina e dimensione sono limitate prima della richiesta. Nessun PIT o `search_after`:
per vedere altri risultati restringere query e filtri. Lo spareggio per `article_id` stabilizza l'ordinamento su un indice
invariato; durante modifiche concorrenti dei documenti non si garantisce una fotografia immutabile dei risultati.

### Validazione e indicizzazione del dump

```bash
python -m wikinews_search validate-dump --dump data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --report data/validation.json
python -m wikinews_search index --dump data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --report data/index-report.json
```

`validate-dump` non richiede Elasticsearch e percorre l'intero archivio in streaming. I report distinguono righe non vuote lette,
articoli validi, scarti per motivo, operazioni bulk riuscite, errori bulk, conteggio finale dei documenti e tempo totale.
ID ripetuti sovrascrivono il documento precedente: le operazioni riuscite possono superare i documenti finali.
Nella sola validazione `indexed_documents` e' `null`, non un conteggio stimato. Con `--limit` il report riguarda il solo prefisso letto.
Gli errori bulk sono registrati e fanno terminare il comando `index` con exit code 1; gli errori di trasporto interrompono il comando.

### Valutazione della rilevanza: confronto A/B/C

Il confronto Standard/BM25, italiano/BM25, italiano/BM25 con `title^3` usa gli indici separati
`itwikinews_hw4_standard` e `itwikinews_hw4_italiano`. `prepare` ricrea solo questi due indici.
Le 27 query e il protocollo manuale in [TESTING.md](TESTING.md) appartengono alla fase esplorativa storica.
La valutazione consolidata usa **18 query, 244 coppie query-documento e due giudici LLM**,
GPT-6 e Claude Opus 5.5: **nessuna validazione umana**. Input congelati, annotazioni originali,
provenienza e ricalcolo offline sono in [experiments/llm-evaluation/README.md](experiments/llm-evaluation/README.md).
Il calcolo delle metriche non richiede Elasticsearch né chiamate ai modelli.

### Benchmark di prestazioni: latenza, capacità e indicizzazione

I benchmark misurano i percorsi Elasticsearch diretto e HTTP Flask, con carico controllato e prove di capacità:
94 query sintetiche, 240 celle, cinque repliche per condizione, 1.336.275 richieste e 20 prove di indicizzazione.
Le misure sono indipendenti dai giudizi di rilevanza. L'[indice degli esperimenti](experiments/README.md)
presenta metodologia, risultati e provenienza della campagna del 18 novembre 2026.
Il [protocollo prestazionale](experiments/performance-20261118/README.md) documenta ambiente originale,
dati grezzi, checksum e ricalcolo delle statistiche **senza rilanciare le prove**.

Il [rapporto di verifica scientifica](experiments/llm-evaluation/FINAL_REPORT.md) distingue calcolo verificabile,
annotazioni non completamente replicabili e limiti di generalizzabilità. L'accordo fra LLM non prova la correttezza umana.
Il [kit e gli asset per la pubblicazione manuale](experiments/RELEASE_ASSETS.md) permettono il ricalcolo
anche senza una copia Git del progetto. La consegna è locale: nessun caricamento remoto automatico.

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest                 # con Elasticsearch attivo (docker compose up -d) esegue tutto
```

Senza Elasticsearch i test di integrazione vengono saltati e restano quelli unitari e web (client finto). La strategia completa e'
in [TESTING.md](TESTING.md). La CI di GitHub Actions avvia un container Elasticsearch ed esegue l'intera suite.

## Note e limiti

* `from + size` e' limitato a 10.000 risultati (`index.max_result_window`); l'interfaccia limita coerentemente le pagine.
* Il formato del dump (`name`, `identifier`, `url`, `namespace`, `date_created`, `categories`, `article_body.html`) segue la documentazione
  Wikimedia Enterprise; la pulizia dell'HTML (`REMOVE_SELECTORS`) e le categorie ignorate (`IGNORED_CATEGORIES`) in `parsing.py` si adattano dopo aver visto i dati reali.
* La soglia di 40 caratteri e' un'euristica per pagine brevi, non un riconoscitore di redirect. Il soft redirect e' riconosciuto tramite HTML.
  `redirects` contiene invece collegamenti entranti e non causa scarto. Si preservano tabelle di contenuto e didascalie;
  le classi note di tabelle di servizio e gli altri selettori esistenti sono rimossi.
* La data usa `date_created`, con fallback a `date_modified`: non e' sempre la data di pubblicazione giornalistica.

Le licenze possono variare tra gli articoli: consultare il campo `license` del dump e la pagina originale.
