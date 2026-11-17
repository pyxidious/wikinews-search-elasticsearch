# Verifiche sul dump e prima esecuzione A/B/C — 17 novembre 2026

Questi sono risultati effettivamente misurati. **Non sono ancora disponibili giudizi manuali di rilevanza**, quindi
non si riportano P@5, MRR@10 o nDCG@10 del corpus reale. Il protocollo e i comandi sono in `TESTING.md`.

## Dati e ambiente

Dump ufficiale del 20 marzo 2025: `itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz`, 72.975.193 byte.
SHA256: `d2c00ef9d7c3db5a3f26adb85b07055673b30b2417653374ada52b7174df474d`.
Scaricato dall'URL della traccia con `curl.exe`, con verifica TLS attiva. Il comando Python `download`
in questo ambiente ha incontrato `CERTIFICATE_VERIFY_FAILED` (certificato scaduto); il fallback Windows e' nel README.

Windows 11 Pro, Intel Core i7-9700K, circa 16 GiB di RAM fisica; Docker Desktop, container con circa 7,7 GiB disponibili,
heap Elasticsearch 1 GiB. Python 3.10.0, client Elasticsearch 8.19.3, server Elasticsearch 8.15.0/Lucene 9.11.1,
Pytest 8.4.2. La prima installazione di Pytest 9.2.0 ha prodotto un errore interno `NodeId._str_cache`:
la verifica locale e' stata eseguita con Pytest 8.4.2 nella `.venv`. Non sono state cambiate le dipendenze del progetto.

## Audit e indicizzazione completa

Il parser originale del commit `48def15` accettava 12.182 record e scartava 79 testi brevi.
La rimozione indiscriminata delle tabelle perdeva citazioni e risultati sportivi/elettorali:
sono stati recuperati 75 record, compresi gli speciali sui mondiali e sulle primarie USA del 2008.
Il record 49166 perdeva una citazione relativa alla statua di Leopoldo II; il record 48882 perdeva la didascalia
dell'ospedale Saint-Pierre. La presenza di entrambi i contenuti e' stata verificata nelle pagine Flask dal dump reale.

Il record 44564, Lua, era gia' scartato per testo breve; ora viene classificato correttamente come soft redirect
tramite `#softredirect`. Non si afferma che fosse precedentemente indicizzato.

| Contatore finale | A (standard) | B/C (italiano) |
|---|---:|---:|
| Record letti | 12.261 | 12.261 |
| Articoli validi / operazioni bulk riuscite | 12.257 | 12.257 |
| Scarti per testo breve | 3 | 3 |
| Scarti per redirect | 1 | 1 |
| Errori bulk | 0 | 0 |
| Documenti unici dopo refresh | 12.209 | 12.209 |
| Tempo di indicizzazione, secondi | 275,17 | 319,10 |
| Store primario dopo flush, byte | 29.146.730 | 27.564.353 |

Le 48 occorrenze con ID ripetuto sono state confermate anche leggendo i record grezzi: l'ultima occorrenza
aggiorna lo stesso `_id`. Non sono 48 errori di caricamento. Si preserva l'ordine del dump, senza aggiungere
strategie di selezione della versione non richieste. Nel dump 1.721 record hanno `redirects` entranti:
non vengono scartati per questo. Solo 242 record hanno `date_created`, mentre tutti hanno `date_modified`;
il filtro temporale va quindi interpretato tenendo conto del fallback, non come data editoriale certificata.

I tempi di costruzione sono misure operative di una singola esecuzione, in parte concorrente con test e audit del parser:
non isolano il costo dell'analyzer e non giustificano conclusioni sulle prestazioni comparative.
Le dimensioni sono fotografie dello store dopo flush, non risultati di un force merge.
L'indice applicativo `itwikinews` non e' stato creato, cancellato o modificato dagli esperimenti.

## Pool e latenze

Eseguite tutte le 27 query di `queries.json`, con identici intenti e corpus. A/B/C hanno prodotto risultati per tutte le query;
questo **non dimostra la rilevanza** dei risultati. Il pool contiene 354 coppie query/documento da giudicare.
I testi completi con URL sono in `data/experiment-real/candidates.jsonl` (file locale, non pubblicato nel repository).
Gli artefatti versionati sono in `results-2026-11-17/`: manifest, run con graduatorie e latenze, template CSV senza giudizi.

Un warm-up escluso per query/configurazione, cinque ripetizioni, ordine ruotato: 135 misure per configurazione.
Latenze client comprensive di rete e deserializzazione, query con aggregazioni/highlighting ed esportazione del corpo.

| Configurazione | p50, ms | p95, ms |
|---|---:|---:|
| A: standard, pesi uniformi | 8,53 | 13,06 |
| B: italiano, pesi uniformi | 8,91 | 14,85 |
| C: italiano, titolo x3 | 9,11 | 13,70 |

Queste latenze sono una misura locale con cache calda, non un test di carico o una garanzia di prestazione.
Il calcolo della qualita' e' predisposto e verificato su giudizi sintetici controllati nei test unitari;
il CSV reale resta intenzionalmente vuoto e `evaluate` rifiuta di trattarlo come ground truth.

## Verifiche e lavoro umano residuo

Suite finale eseguita con:

```powershell
$env:WIKINEWS_DUMP = 'data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz'
.venv\Scripts\python -m pytest -q --cov=wikinews_search --cov-report=term-missing --junitxml=data/pytest-final.xml
```

**116 test superati, zero saltati, 174,13 secondi; coverage complessiva 93%.** La differenza rispetto al 97% storico
dipende anche dall'aggiunta del modulo sperimentale e dei suoi percorsi CLI: la copertura non e' una misura di qualita' del ranking.
Conservati tutti i test precedenti; il test dell'ordinamento atteso e' stato aggiornato per includere lo spareggio stabile.

Verificati su Elasticsearch reale gli operatori OR, AND, esclusioni, frasi con trattini, prefissi e fuzzy, nonche'
lo spareggio su 10.003 documenti con punteggio/data uguali. Verificati anche homepage, ricerca, API e lettura di due
articoli dal corpus completo tramite client Flask. Restano da eseguire la valutazione indipendente dei 354 candidati,
il confronto B-A/C-B con metriche di qualita', e una demo visiva nel browser per la presentazione.
Il testo originale delle slide non e' disponibile nel repository: i collegamenti didattici seguono i principi riportati nella traccia.
