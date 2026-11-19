# Consolidamento scientifico — 19 novembre 2026

## Esito verificato, distinto dalla generazione delle etichette

Ricalcolo offline, senza LLM e senza accessi Elasticsearch: 18 query, 244 coppie, 210 articoli, 15 gruppi.
I CSV originali sono completi, i ranking e il pool coincidono, non vi sono duplicati o gradi estranei.
I valori seguenti sono ricalcolati dai due CSV, non imposti dai risultati attesi.

| Configurazione | GPT-6 nDCG@10 | Claude Opus 5.5 nDCG@10 |
|---|---:|---:|
| A | 0.8827851382 | 0.8193258153 |
| B | 0.9607030353 | 0.8916405090 |
| C | 0.8925997529 | 0.8193511784 |

Accordo esatto **191/244 = 0.7827868852**, kappa quadratico **0.8016012009**;
53 disaccordi. Matrice (GPT righe, Claude colonne, ordine 0/1/2): `[[45, 0, 0], [10, 25, 2], [4, 37, 121]]`.
L'accordo non costituisce validazione umana o prova della correttezza delle etichette.

Verificati **345 valori** storici, incluse medie, IC, sensibilità e leave-one-group-out:
zero discrepanze oltre tolleranze assoluta/relativa 1e-12. Le differenze entro arrotondamento non vengono corrette
nelle qrels. NumPy 2.2.6 è l'ambiente del nuovo ricalcolo, non una versione recuperata dai log storici.
17 test automatici di integrità/formule/protezione dello script umano passati; vedere `results/integrity_tests.log`.

## Effetti e sensibilità: evitare conclusioni dalle sole medie

| Giudice | Contrasto | Delta nDCG medio | IC95 principale | Delta senza Brexit |
|---|---|---:|---|---:|
| GPT-6 | B-A | +0.077918 | [+0.008807; +0.151040] | +0.082501 |
| GPT-6 | C-B | -0.068103 | [-0.195312; -0.000065] | -0.013286 |
| Claude-Opus-5.5 | B-A | +0.072315 | [+0.021303; +0.132868] | +0.076568 |
| Claude-Opus-5.5 | C-B | -0.072289 | [-0.205390; +0.003765] | -0.017718 |

B ha la media nDCG più alta sotto entrambe le annotazioni di questo pool. Non è una prova universale di
superiorità dell'analyzer né una certificazione umana. A e C sono vicine; il contrasto C−B si riduce fortemente
senza Brexit. Il segno resta stabile nei leave-one-group-out, ma l'ampiezza dell'effetto e gli IC sono sensibili
ai gruppi: consultare tutte le query e gli output completi, non selezionare soltanto un intervallo favorevole.

Il bootstrap principale usa gruppi, RNG Python e nearest-rank; l'audit post-hoc senza accenti usa RNG NumPy
e quantili lineari. Entrambi sono riprodotti con 10.000 estrazioni e seed 20261118. Non si sostituisce una
procedura all'altra per far coincidere gli IC. Le sensibilità sono esplorative, senza correzione per confronti
multipli; gli IC non incorporano errori sistematici degli LLM. I 53 casi qualitativi sono verificati rispetto
ai gradi e agli hash dei documenti, ma le categorie dell'analista non vengono rigenerate né promosse a qrels.

## Prestazioni fisiche, indipendenti dai giudizi AI

Ricalcolate dai raw pubblicabili 1.336.275 richieste, 240 celle e 20 caricamenti: nessun nuovo benchmark,
nessuna creazione, cancellazione, apertura o chiusura di indici durante il consolidamento. Risultati
entro tolleranze assoluta 1e-9 / relativa 1e-12, senza discrepanze nei riepiloghi verificati.
Le cinque repliche sono le unità del bootstrap prestazionale; le richieste non sono repliche indipendenti.
113/120 celle di capacità soddisfano il criterio prefissato; sette falliscono per CV delle finestre.
I due errori client di socket rimangono nei raw. Manifest e snapshot originali forniscono CPU/RAM,
Windows, Python/dipendenze, ES/Lucene, Docker/immagine, JVM, nodi/shard/repliche, carico, warm-up e durata.
Nessuna condizione hardware è ricostruita retroattivamente da questa macchina.

L'asset grezzo curato è pronto, con SHA in `../performance-20261118/RAW_DATA.json`, ma non è stato caricato
in una release/deposito: l'URL resta non assegnato e deve essere aggiunto dal pubblicatore. Gli originali
ZIP di input rimangono localmente nello staging; non sono automaticamente materiale da pubblicare.

## Provenienza mancante e limiti sostanziali

**Non è raggiunta una riproducibilità completa delle annotazioni.** Mancano i prompt originali, i messaggi
di sistema, le date delle annotazioni, temperature/top_p/seed LLM, limiti token, log delle chiamate,
strumenti/batch/retry e porzioni effettivamente lette per ciascun documento. Il nome GPT-6 non specifica
un identificativo API o snapshot; per Claude `claude-opus-5-5` e modalità High sono riferiti, ma manca
una risposta API che documenti lo snapshot servito. I timestamp ZIP non sono usati come date dell'annotazione.
Le rubriche storiche sono narrative registrate, non prompt recuperati. Non è inventato un prompt sostitutivo.

Claude ha riferito lettura non integrale di alcuni articoli lunghi; anche il protocollo GPT-6 menziona lettura
mirata. L'indipendenza e la cecità sono dichiarate, non verificabili da trascrizioni/API log assenti.
**Nessuna validazione umana.** Accordo elevato può coesistere con bias condivisi, errori o interpretazioni
troppo permissive/restrittive della soglia 1/2. L'audit è post-hoc e non è un terzo giudice indipendente.

I testi integrali non sono pubblicati: i 210 articoli del pool hanno metadati CC-BY-SA-4.0 nel dump,
mentre la pagina copyright attuale del progetto indica CC BY 4.0. Si conservano URL, attribuzioni,
licenze per articolo e hash, senza uniformare retroattivamente le licenze. La ricostruzione locale dal
dump e dal parser originali è stata verificata: SHA del file cieco completo
`5a8e255c6028f73e5aa9092b7ebd8c6191743d8b14134f883de59d46c6aa6d4e`, esattamente uguale all'input storico.
Non servono i testi per le metriche. Nessun indice è necessario per questa ricostruzione.

## Livelli di riproducibilità

**A. Calcolo:** verificato sui file congelati pubblicabili, con tolleranze e comando documentati; calcolatori
indipendenti dall'applicazione e dalle API LLM. Gli output originali restano immutati e distinti dai ricalcoli.

**B. Annotazione LLM:** incompleta per le lacune sopra elencate e per la variabilità dei modelli; una nuova
annotazione è un nuovo esperimento, non il recupero delle etichette storiche.

**C. Prestazioni:** statistiche originali ricalcolabili; nuove misure richiedono ambiente equivalente e possono
differire. Workstation condivisa, cache calda, finestre brevi, generatore locale e connessioni HTTP sono limiti.

**D. Generalizzabilità:** corpus storico italiano, query sintetiche deliberate, pooling top-10 e due giudici AI.
Non è un campione probabilistico di utenti, non stima recall globale né accuratezza fattuale delle notizie;
non giustifica validità universale o confronti di qualità certificati da esseri umani.

Le istruzioni operative sono in README.md; prompt/modelli in PROMPT_PROVENANCE.md/.json; sorgenti e
deduplicazioni in SOURCE_ARCHIVES.json; file correnti in manifest.json e RESULTS_INDEX.json.

## Chiusura dopo l?interruzione di corrente

Nuova copia indipendente da 171 file originali, tutti verificati SHA-256 prima di eseguire gli script. I tre file NUL della vecchia copia temporanea non sono stati modificati n? usati. Nuovo ambiente Python 3.10.0, NumPy 2.2.6: ricalcolo di tutti i 345 valori LLM e dei raw prestazionali senza discrepanze; ricostruzione integrale dell?input cieco con hash storico identico. Ambiente e prove in `results/clean_environment.json` e `results/recovery_verification.json`. Nessun nuovo esperimento fisico o giudizio.

Il CSV Claude aggiuntivo ? stato ritrovato e verificato: SHA-256 `8001cd894c92cd34b4ed550fd7a92152f95397b5f5fe92a61e66c7ac808c344b`. ? identico all?originale gi? incluso: nessun duplicato aggiunto. La scoperta non recupera la data dell?annotazione.

Consegna permanente: `C:\Users\proti\Desktop\wikinews-benchmark-publication\`. Due ZIP curati, `SHA256SUMS` e `RELEASE_MANIFEST.json`; niente caricamento automatico. Procedura e comandi esterni in [RELEASE_ASSETS.md](../RELEASE_ASSETS.md). Sono esclusi staging, archivi originali ridondanti, testi integrali e ambienti. Una vista Markdown del rapporto storico corregge cinque percorsi relativi; l?originale byte per byte resta disponibile e la trasformazione ? registrata in `../performance-20261118/SOURCE.json`.
