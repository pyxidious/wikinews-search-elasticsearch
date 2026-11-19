# Benchmark fisico del 18 novembre 2026: originali e ricalcolo

Questa directory conserva le misure originali, separate dalle etichette LLM. Nessuna prova prestazionale
è stata rieseguita durante il consolidamento, nessun indice è stato modificato o interrogato.

## Dati e distribuzione

`original/` contiene copie byte per byte dei workload, schedule, risultati per cella, CSV di indicizzazione,
riepiloghi/IC, manifest, snapshot cluster/hardware, versioni software e log. `SOURCE.json` lega questa selezione
all'originale `results.zip` (SHA-256 `411aad94a24efeea17f08057c9d2bf82eb12a39dc72c71b7eadc0ce7009bd973`).
Il vecchio registro `original/artifact_checksums.json` descrive l'intero archivio originale, non questa selezione;
il registro corrente è `manifest.json`.

`search_raw.csv` (223.634.590 byte) e `telemetry.jsonl` (30.870.892 byte) sono in un **nuovo asset curato**
`performance-raw-20261118.zip`. Contiene solo questi due file immutati e i loro checksum, senza testi integrali.
Il nome, SHA-256 e dimensione dell'asset sono in `RAW_DATA.json`. L'asset è preparato localmente per il deposito
come allegato a una release o in un archivio scientifico, con consegna permanente in
`C:\Users\proti\Desktop\wikinews-benchmark-publication\`; **non è stato caricato** e `download_url` resta `null`.
Il pubblicatore dovrà fornire un URL reale/DOI e mantenere esattamente quei byte. Gli ZIP sorgente delle
annotazioni non sono asset di pubblicazione e restano ignorati nello staging.

Il kit autonomo e la procedura di allegato manuale sono descritti in
[RELEASE_ASSETS.md](../RELEASE_ASSETS.md). Il kit include i file pubblicabili e i sorgenti applicativi
originali invariati; non include dump, testi ricostruiti, ambiente Python, archivi sorgente o dati grezzi grandi.

I file grezzi grandi non vanno copiati nei normali file del repository. Non si è configurato Git LFS né eseguita
alcuna operazione Git. Il ricalcolo della rilevanza non dipende da questo asset, dai testi o dal dump.

## Ricalcolo offline dalle misure grezze

Scaricare/procurarsi l'asset, verificare il suo SHA-256 con `RAW_DATA.json`, quindi:

```bash
python -B experiments/performance-20261118/recompute.py --raw-archive /path/performance-raw-20261118.zip --out .reproduction/performance
```

Servono solo Python 3.10+ e stdlib. Lo script verifica l'archivio e ciascun membro, legge tutte le singole
richieste e ricalcola p50/p95 client, tempi ES `took`, componenti richiesta/dispatch, errori, throughput,
finestre di capacità e riepiloghi/contrasti con IC. Per il throughput usa il tempo trascorso per cella
**misurato e registrato** in `search_cells.json` (incluso drain), non una durata ricostruita dagli estremi delle richieste.
Ricalcola inoltre durata, documenti/s, errori Bulk e store dai 20 run di indicizzazione.
I valori p50/p95 salvati per cella sono controlli, non input al loro ricalcolo.

Le statistiche sono confrontate con gli output originali: tolleranze assoluta **1e-9** e relativa **1e-12**.
`verification.json` elenca ogni discrepanza e il programma fallisce in caso di mancata corrispondenza.
I risultati non sono corretti per ottenere i valori attesi. La telemetria grezza resta disponibile per analisi
delle risorse; il suo riepilogo originale è conservato senza inventare nuove condizioni hardware.

## Ambiente e protocollo effettivamente registrati

- CPU Intel Core i7-9700K, 8 core/logici; RAM fisica 17.106.173.952 byte (15,93 GiB).
- Windows 11 Pro, versione kernel 10.0.26300; dettagli originali in `original/hardware.json`.
- Python 3.10.0; Elasticsearch client 8.19.3, Flask 3.1.3, BeautifulSoup 4.15.0, lxml 6.1.3.
  Tutte le dipendenze registrate: `environment_packages.json`; tool grafici: `plot_environment.json` e lockfile.
- Elasticsearch 8.15.0, Lucene 9.11.1; Docker e immagine: `docker_version.json`, `docker_image_identity.txt`,
  `docker_hostconfig.json`. JVM, OS VM e impostazioni reali: `cluster_before.json`/`cluster_after.json`.
- Un nodo, heap JVM massimo **1.073.741.824 byte**, 1 shard primario e 0 repliche per indice.
- A: standard/BM25 uniforme; B: analyzer italiano custom/BM25 uniforme; C: stesso indice B, `title^3`.
- 94 query sintetiche deliberate, distinte dalle 27 diagnostiche; seed 20261118 e hash congelati.
- 240 celle: 2 percorsi × 2 scenari × 4 limiti di client (1,4,8,16) × 3 configurazioni × 5 repliche.
- Warm-up 32 richieste seriali per cella, escluso. Blocchi completi randomizzati, cache naturalmente calda.
- Carico controllato: 96 arrivi distanziati di 125 ms, **8 richieste/s aggregate**, con coda esplicita.
  Con carico basso i client configurati sono un massimo: picchi osservati di 1–2 richieste in volo.
- Capacità: ciclo chiuso per 30 s e drain; tre finestre da 10 s. Tutti i livelli di concorrenza raggiunti.
  Criterio prefissato: p95≤500 ms, errori≤1%, CV throughput finestre≤0,15; **113/120** celle lo soddisfano,
  sette falliscono per variabilità. Non è il massimo assoluto o una prova di stabilità di ore.
- Percorso diretto ES e HTTP Flask `/` con rendering HTML, Werkzeug threaded, urllib e loopback.
  Payload Web normale (size 10, highlight e faccette), senza corpo integrale per esportazione candidati.
  Pool ES 32 connessioni; endpoint 127.0.0.1, timeout 30 s, retry disabilitati, request cache disabilitata.
- 1.336.275 richieste misurate, 2 errori client Windows `OSError 10048` mantenuti, non attribuiti all'analyzer.
- 20 caricamenti: 5 per analyzer in ciascuna fase (HTML completo e preprocessato), ordine alternato;
  12.257 operazioni, 12.209 documenti unici, zero errori Bulk. Nuovi indici tutti conservati.
  Refresh periodico disabilitato durante ingest, refresh esplicito finale; flush separata dalla durata;
  store primario misurato dopo flush, senza force-merge. La dispersione dello store è un dato operativo,
  non prova di corpus differente: hash delle sorgenti finali identico in tutti i 20 indici.

`client_ms` parte dal tempo programmato, `service_ms` dall'avvio effettivo, `queue_ms` misura dispatch;
`es_took_ms` è il tempo intero dichiarato da ES. Non sono la stessa grandezza e i percentili non si sommano.
I fallimenti sono esclusi dai percentili dei successi ma contati separatamente e conservati nei raw.
Il throughput è successi/tempo reale della cella. La finita finestra controllata può dare circa 8,08/s
pur avendo intervalli offerti esattamente pari a 125 ms (prima richiesta a t=0).

Bootstrap: 10.000 campioni percentile, seed 20261118, **cinque repliche sperimentali**, non milioni di richieste
come osservazioni indipendenti. Confronti appaiati per replica B−A/C−B e italiano−standard.
IC non corretti per confronti multipli e campione di run piccolo. Intervalli descrittivi e dataset sintetico
non provano significatività generale o validità per utenti reali.

## Ripetizione delle misure fisiche, distinta dal ricalcolo

`historical/benchmark.py` e gli strumenti originali sono conservati per provenienza, con percorsi macchina
specifici e comandi capaci di creare/aprire/chiudere nuovi indici. **Non sono il comando di ricalcolo offline**.
Una nuova campagna richiede ambiente equivalente, nuova directory/namespace e controllo del carico;
non va eseguita automaticamente sopra dati o indici esistenti. Nessuna promessa di latenze identiche.
Il report del giorno 18 in `historical/` descriveva ancora una validazione umana futura: è storico,
non il protocollo delle successive annotazioni AI. Vedere il [rapporto corrente](../llm-evaluation/FINAL_REPORT.md).
