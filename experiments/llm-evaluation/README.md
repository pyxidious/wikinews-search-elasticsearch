# Valutazione congelata AI-only: ricalcolo offline

18 query sintetiche, 244 coppie query-documento, 210 articoli distinti, 15 gruppi.
Due annotazioni dichiarate indipendenti: GPT-6 e Claude Opus 5.5 High. **Nessuna validazione umana.**
Le 27 query in `../queries.json` e `../results-2026-11-17/` restano una fase esplorativa separata.

## 1. Preparare l'ambiente

Usare Python 3.10+ in un ambiente separato dall'applicazione. Installazione iniziale delle dipendenze:

```bash
python -m venv .reproduction/venv
# Linux/macOS: source .reproduction/venv/bin/activate
# Windows PowerShell: .reproduction/venv/Scripts/Activate.ps1
python -m pip install -r experiments/llm-evaluation/requirements-reproduction.txt
```

NumPy 2.2.6 è la versione scelta e verificata per **questo ricalcolo**, non una versione storica
inventata per gli LLM o l'audit originale. L'analisi principale è stdlib; NumPy è necessario per
riprodurre esattamente la procedura post-hoc dell'audit sugli accenti.

## 2. Controllare e ricalcolare

Dalla radice del repository, anche senza rete, senza chiavi API, senza Docker e senza Elasticsearch:

```bash
python -B -m unittest discover -s experiments/llm-evaluation/tests -v
python -B experiments/llm-evaluation/reproduce.py --out .reproduction/llm
```

Il comando verifica `manifest.json`, la completezza dei due CSV originali e gli ID. Crea un adattatore ZIP
temporaneo dai soli input pubblicati e invoca il **calcolatore AI originale**, conservato immutato in
`historical/compare_llm_judges.py`: ricalcola realmente ogni metrica dai gradi e dai ranking, non dalle
tabelle di riferimento. Non importa né aggira lo script umano protetto. I suoi percorsi di metadata
temporanei vengono normalizzati nei nuovi output; gli originali storici non sono riscritti.

`verification.json` confronta i valori ricalcolati con quelli storici: tolleranze assoluta e relativa
**1e-12**. Un disaccordo produce un elenco di campi e un codice di uscita non zero, mai una modifica alle qrels.
Il rapporto corrente è [FINAL_REPORT.md](FINAL_REPORT.md). `RESULTS_INDEX.json` identifica gli output
consolidati e i riferimenti riutilizzati quando identici, evitando copie byte per byte ridondanti.

## 3. Input pubblicati e provenienza

- `data/queries.json`: intenti, categorie e gruppi originali.
- `data/pool.metadata.jsonl`: ordine del pool, ID ciechi, titoli/URL, lunghezze e SHA-256 dei testi;
  ordine originale dei campi conservato per la ricostruzione esatta.
- `data/ranking_private.json`: ranking A/B/C originali e mapping `query_id|candidate_id → document_id`.
  Le query incluse in questo JSON originale devono coincidere con `queries.json`.
- `data/qrels_gpt6.original.csv`, `data/qrels_claude.original.csv`: entrambi completi e immutati.
- `data/qualitative_audit_53.original.csv`: audit successivo, non nuove qrels.
- `SOURCE_ARCHIVES.json`: inventario di tutti i membri degli ZIP sorgente, SHA, destinazioni canoniche,
  duplicati e file derivabili non ripubblicati. Gli ZIP sorgente restano in staging, non nel pacchetto pubblicabile.
- `historical/`: protocolli, report e codice originali con stato storico esplicito.
- `references/`: tabelle pubblicate usate soltanto dopo il ricalcolo, come controllo esterno.
- [PROMPT_PROVENANCE.md](PROMPT_PROVENANCE.md) e `.json`: dati noti e informazioni non registrate.
- [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md): protocollo corrente AI-only.

Nella prima raccolta `qrels_second_llm.csv` non era stato trovato separatamente. Nell'audit successivo
è presente in `experiments/reproducibility-inputs/`: il suo SHA-256 è
`8001cd894c92cd34b4ed550fd7a92152f95397b5f5fe92a61e66c7ac808c344b`, identico al CSV Claude estratto
dallo ZIP e all'hash storico in `agreement.json`. È registrato come ulteriore sorgente dello stesso
file canonico, senza alterare o duplicare le annotazioni. GPT-6 compare in due ZIP con contenuto identico:
anche qui è conservata una sola copia canonica. Gli originali nello staging non sono stati cancellati.

Per il kit autonomo, l'asset grezzo e i checksum della consegna permanente vedere
[RELEASE_ASSETS.md](../RELEASE_ASSETS.md). I prompt e i parametri storici mancanti restano mancanti:
la verifica dei calcoli non rende replicabile la generazione originale delle etichette.

## 4. Definizioni statistiche

nDCG@10 **primaria**, con guadagno `2^grade-1`, sconto `log2(rank+1)`, IDCG sui dieci migliori gradi del
pool giudicato. P@5 e MRR@10 sono secondarie: rilevante = grado >0, denominatore P@5 sempre 5.
Query senza rilevanti nel pool: metriche a zero per convenzione, con elenco esplicito; non si inferisce
assenza di rilevanti nell'intero corpus. Le medie sono macro sulle 18 query, non sulle 244 coppie.

Contrasti appaiati B−A e C−B per query; i medesimi ranking sono usati da entrambi i giudici.
Bootstrap principale: 10.000 estrazioni con rimpiazzo di **15 gruppi**, seed Python `random.Random(20261118)`;
si includono tutte le query dei gruppi estratti e si calcola la media per query. I gruppi accoppiano
lavoratore/lavoratori, studente/studenti e università/universita; gli altri sono singoli. Percentili nearest-rank
`ceil(p*N)`. L'estimando resta una media per query, non una media di medie dei gruppi.

Accordo: matrice 3×3 (righe GPT-6, colonne Claude), accordo esatto e binario, kappa quadratico e lineare.
Il bootstrap dell'accordo ricampiona i gruppi mantenendo insieme tutte le coppie delle query selezionate.
Kappa con disaccordo atteso nullo è indefinito, non forzato a uno.

Sensibilità: esclusione Brexit, accenti, entrambi; trasformazioni esplorative grado 1→0 e 1→2 applicate
solo in memoria, separatamente per giudice. Leave-one-group-out elimina ciascuno dei 15 gruppi senza
cambiare le etichette. L'audit storico senza accenti usa invece `numpy.random.default_rng(20261118)`
(PCG64), `choice`, e `numpy.quantile(method='linear')`: **stesso seed numerico non significa stessa procedura**.
Sono riprodotti entrambi i metodi, senza sostituirne gli intervalli. La versione NumPy storica non era registrata.
Tutte le sensibilità/audit sono esplorativi e post-hoc; non danno nuovi giudizi né adjudication.

Gli IC non modellano errori sistematici degli LLM, lettura incompleta o selezione non probabilistica delle query;
non sono corretti per confronti multipli. Un IC prossimo a zero non autorizza conclusioni universali.

## 5. Ricostruire gli input testuali, se necessario

Per le metriche non serve alcun testo. Per verificare il materiale documentale originale:

1. Procurarsi il dump ufficiale esatto indicato in `data/corpus_reference.json`.
2. Installare le dipendenze del parser riportate nel benchmark originale (`beautifulsoup4==4.15.0`, `lxml==6.1.3`;
   gli altri moduli usati per questa ricostruzione sono stdlib).
3. Eseguire:

```bash
python -B experiments/llm-evaluation/reconstruct_candidates.py --dump /path/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --out .reproduction/reconstructed/blind_candidates.jsonl
```

Sono controllati hash del dump, sorgenti del parser, titoli/URL, contenuto di ogni testo e SHA dell'intero
file cieco, compresi ordine delle chiavi e terminatori CRLF originali. Un file già esistente non viene sovrascritto.
Il procedimento non crea indici. Fonte e condizioni di riuso: [LICENSING.md](LICENSING.md).

## 6. Quattro livelli da non confondere

**A — Calcolo:** verificabile dai file pubblicati, senza LLM, entro tolleranze numeriche esplicite.

**B — Annotazione:** non completamente replicabile; prompt, messaggi di sistema, date e parametri sostanziali
mancano. Lo stesso nome di modello non assicura lo stesso snapshot o gli stessi gradi.

**C — Prestazioni:** [protocollo distinto](../performance-20261118/README.md), misure fisiche originali e ambiente
documentato; ricalcolo offline distinto da una nuova prova su hardware equivalente. Non si promettono tempi identici.

**D — Generalizzabilità:** corpus italiano storico, query sintetiche, pooling top-10, cluster locale e giudici AI.
Accordo non significa correttezza, nessun recall globale o validità universale. Non è stata effettuata validazione umana.
