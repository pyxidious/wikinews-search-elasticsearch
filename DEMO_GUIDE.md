# Demo live di Wikinotizie Search

La demo usa l’applicazione Flask del repository e un vero indice Elasticsearch. Le schede di esempio
in homepage eseguono ricerche nuove; i dati di questa guida e di `scripts/demo_queries.json` sono
aspettative misurate per la verifica, non una sorgente di risultati per l’interfaccia.

## Avvio rapido su Windows

Prerequisiti: Python 3.10+, Docker Desktop in esecuzione con container Linux, porte 9200 e 5000 libere,
dipendenze Python installate e corpus italiano già indicizzato. Dalla radice del repository:

```powershell
# Solo la prima volta, se .venv non esiste:
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Avvio normale: Elasticsearch, controllo indice, Flask e browser
.\scripts\start_demo.ps1
```

Il launcher prova `itwikinews` e, se assente, `itwikinews_hw4_italiano`. Se si specifica `-IndexName`
oppure `ES_INDEX`, usa solo quel nome e si interrompe se manca. Controlla l’analyzer italiano; non crea,
cancella, apre/chiude né ricostruisce indici. `--no-recreate` preserva il container esistente.
Per questa macchina l’avvio esplicito è:

```powershell
.\scripts\start_demo.ps1 -IndexName itwikinews_hw4_italiano
```

Apri **http://127.0.0.1:5000/**. Il browser automatico si apre dopo che `/health` risponde; `-NoBrowser`
disattiva questa apertura. `-SkipDocker` usa Elasticsearch già in esecuzione. `-Port 5001` sceglie una
porta alternativa; lo smoke test deve ricevere `--base-url http://127.0.0.1:5001` in quel caso.
Se la policy PowerShell impedisce lo script, si possono eseguire i comandi manuali seguenti senza
cambiare la policy. Fermare Flask con **Ctrl+C** nel terminale che lo esegue.

### Avvio manuale equivalente

```powershell
docker compose up -d --no-recreate elasticsearch
# Attendere che Elasticsearch risponda; questo comando legge soltanto il conteggio:
.venv\Scripts\python.exe -m wikinews_search stats --es-url http://127.0.0.1:9200 --index-name itwikinews_hw4_italiano
.venv\Scripts\python.exe -m wikinews_search serve --es-url http://127.0.0.1:9200 --index-name itwikinews_hw4_italiano
# Aprire http://127.0.0.1:5000/ nel browser.
```

### Nuova installazione senza indice

Un clone Git non include il dump né il volume Docker. In assenza di un indice italiano, il launcher si
ferma: questo è intenzionale. Prima di una prima indicizzazione, verificare con `stats` che il nome
scelto non identifichi un indice da conservare. Poi, solo dopo una decisione esplicita dell’operatore:

```powershell
.venv\Scripts\python.exe -m wikinews_search download
# Operazione esplicita: RICREA l’indice di destinazione, anche se esiste già.
.venv\Scripts\python.exe -m wikinews_search index --index-name itwikinews
.\scripts\start_demo.ps1 -IndexName itwikinews
```

Non è un comando di avvio e non va eseguito durante la presentazione. La preparazione di questa demo
ha usato l’indice italiano esistente, senza eseguire `index` o `prepare` e senza creare alias.
Per il fallback TLS su Windows vedere [README.md](README.md#uso).

## Configurazione e provenienza della verifica

- Verifica funzionale del **19 novembre 2026**, Elasticsearch 8.15.0.
- Indice: `itwikinews_hw4_italiano`, UUID `HOHk1UTyS-q1PgetBbfaOQ`, **12.209 documenti**.
- Dump: `itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz`, del **20 marzo 2025**;
  SHA-256 `d2c00ef9d7c3db5a3f26adb85b07055673b30b2417653374ada52b7174df474d`.
- Default applicativo **B**: analyzer italiano personalizzato, BM25, campi `title` e `body` con pesi uniformi.
  B ha la migliore nDCG@10 media sotto i due giudici LLM nel pool studiato; non c’è validazione umana.
  Il confronto storico A/B/C e i suoi dati restano immutati. B e C condividono l’indice italiano.
- Le verifiche confrontano ricerca diretta e API HTTP. Conteggi, titoli e ordine possono variare con un
  corpus, parser, analyzer, pesi o versione diversi: un fallimento dello smoke test va indagato, non
  aggirato sostituendo conteggi arbitrari.

## Query realmente verificate

I totali sono tutte le corrispondenze, non il numero di elementi della pagina (10). I primi tre titoli
seguenti sono quelli misurati; i link aprono ricerche reali sulla demo locale. Per AND usare `+`, per OR
`|` o spazi, per NOT `-`. In un URL il `+` deve essere codificato come `%2B`: i link e il form lo fanno.

### 1. Ricerca semplice

Query: `terremoto`. Parametri aggiuntivi: **nessuno**.

**156 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=terremoto).

1. Terremoto in Sicilia — ID `5619`.
2. Terremoto nel salernitano — ID `2579`.
3. Messico, terremoto di magnitudo 7.4 — ID `49285`.

Perché mostrarla: Parte da un evento riconoscibile: mostra gli snippet, apri il primo articolo e torna alla seconda pagina dei risultati.

Limiti: È una corrispondenza testuale: una menzione nel corpo non implica che il terremoto sia il tema principale.

### 2. Stemming: singolare

Query: `elezione`. Parametri aggiuntivi: **nessuno**.

**621 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=elezione).

1. Rinviate le elezioni in Basilicata — ID `991`.
2. Elezioni italiane 2008, la DC rinuncia al rinvio delle elezioni — ID `19632`.
3. Elezioni 2006: come si vota — ID `5444`.

Perché mostrarla: Il singolare recupera titoli al plurale; confronta subito con elezioni.

Limiti: Lo stemming raggruppa forme lessicali, non sinonimi o significati. Non è una valutazione umana della rilevanza.

### 3. Stemming: plurale

Query: `elezioni`. Parametri aggiuntivi: **nessuno**.

**621 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=elezioni).

1. Rinviate le elezioni in Basilicata — ID `991`.
2. Elezioni italiane 2008, la DC rinuncia al rinvio delle elezioni — ID `19632`.
3. Elezioni 2006: come si vota — ID `5444`.

Perché mostrarla: Confronto controllato con elezione: conteggio, prima pagina e token analizzati sono identici (elezion).

Limiti: Il test confronta il totale e gli ID della prima pagina, non esporta tutti i 621 documenti; verifica inoltre che i token siano identici.

### 4. Normalizzazione senza accento

Query: `citta`. Parametri aggiuntivi: **nessuno**.

**1.207 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=citta).

1. Milano: Una città per tutti ? Il futuro di Città Studi si chiama Università — ID `47588`.
2. Degrado nel parco della stazione "La Rustica Città" — ID `38481`.
3. Città del Messico: crolla viadotto della metropolitana — ID `50054`.

Perché mostrarla: La forma senza accento recupera città nei titoli e nel testo; confronta subito con città.

Limiti: È normalizzazione degli accenti, non correzione ortografica generale. La query è ampia e mescola argomenti.

### 5. Normalizzazione con accento

Query: `città`. Parametri aggiuntivi: **nessuno**.

**1.207 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=citt%C3%A0).

1. Milano: Una città per tutti ? Il futuro di Città Studi si chiama Università — ID `47588`.
2. Degrado nel parco della stazione "La Rustica Città" — ID `38481`.
3. Città del Messico: crolla viadotto della metropolitana — ID `50054`.

Perché mostrarla: Conteggio, prima pagina e token analizzati sono identici a citta (token citta).

Limiti: Il confronto verifica totale, prima pagina e token; non esporta tutti i 1.207 documenti.

### 6. Frase analizzata

Query: `"banca centrale"`. Parametri aggiuntivi: **nessuno**.

**33 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=%22banca+centrale%22).

1. Le banche centrali tagliano i tassi — ID `23916`.
2. Nessuna sorpresa dal comunicato della BCE — ID `46378`.
3. Libano in piena crisi — ID `49218`.

Perché mostrarla: Il primo titolo contiene banche centrali: la frase mantiene ordine e posizioni, ma usa stemming e stopword.

Limiti: Non promettere una sottostringa letterale. “Libano in piena crisi” corrisponde nel corpo, non nel titolo.

### 7. AND

Query: `Roma + Milano`. Parametri aggiuntivi: **nessuno**.

**1.157 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=Roma+%2B+Milano).

1. Gay pride a Roma e Milano — ID `20810`.
2. Omicidio Sandri: atti vandalici nelle caserme di Roma e Milano — ID `17112`.
3. Roma: allarme bomba su un aereo proveniente da Milano — ID `28756`.

Perché mostrarla: Confronta il totale con OR: AND restringe alle corrispondenze di entrambi i termini.

Limiti: Roma e Milano possono indicare squadre di calcio. Le parole AND/OR/NOT digitate letteralmente non sono gli operatori richiesti.

### 8. OR

Query: `Roma | Milano`. Parametri aggiuntivi: **nessuno**.

**3.292 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=Roma+%7C+Milano).

1. Gay pride a Roma e Milano — ID `20810`.
2. Omicidio Sandri: atti vandalici nelle caserme di Roma e Milano — ID `17112`.
3. Roma: allarme bomba su un aereo proveniente da Milano — ID `28756`.

Perché mostrarla: OR amplia il totale da 1.157 a 3.292; i primi tre titoli restano uguali perché contengono entrambi i termini.

Limiti: Un totale maggiore non implica un diverso primo risultato né maggiore rilevanza. Anche lo spazio tra termini indica OR.

### 9. NOT

Query: `elezioni -Roma`. Parametri aggiuntivi: **nessuno**.

**536 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=elezioni+-Roma).

1. Rinviate le elezioni in Basilicata — ID `991`.
2. Elezioni italiane 2008, la DC rinuncia al rinvio delle elezioni — ID `19632`.
3. Elezioni 2006: come si vota — ID `5444`.

Perché mostrarla: L’esclusione riduce elezioni da 621 a 536. Il controllo automatico verifica anche la relazione con elezioni + Roma.

Limiti: I primi tre titoli restano uguali: mostra il conteggio. L’esclusione opera su titolo e corpo analizzati, anche quando Roma non compare nel titolo.

### 10. Filtro categoria

Query: `elezioni`. Parametri aggiuntivi: **category=Italia**.

**303 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=elezioni&category=Italia).

1. Rinviate le elezioni in Basilicata — ID `991`.
2. Elezioni italiane 2008, la DC rinuncia al rinvio delle elezioni — ID `19632`.
3. Elezioni 2006: come si vota — ID `5444`.

Perché mostrarla: Digita elezioni e imposta Categoria = Italia, oppure usa la faccetta Italia della ricerca non filtrata.

Limiti: La categoria è un valore esatto keyword, con maiuscole significative. Una pagina può appartenere a più categorie e la faccetta mostra solo le 12 più frequenti.

### 11. Filtro anno

Query: `elezioni`. Parametri aggiuntivi: **year=2008**.

**117 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=elezioni&year=2008).

1. Elezioni italiane 2008, la DC rinuncia al rinvio delle elezioni — ID `19632`.
2. Bielorussia: in 25mila contestano le elezioni — ID `5189`.
3. Speciale Elezioni politiche italiane 2008 — ID `18682`.

Perché mostrarla: Digita elezioni e imposta Anno = 2008; osserva il cambiamento nei primi titoli.

Limiti: L’anno viene dalla data indicizzata: date_created, con fallback a date_modified. Non sempre coincide con la data giornalistica, come mostra il titolo sulla Bielorussia.

### 12. Ordinamento per data

Query: `terremoto`. Parametri aggiuntivi: **sort=date**.

**156 risultati** · [Esegui la ricerca](http://127.0.0.1:5000/?q=terremoto&sort=date).

1. Milano: deragliato treno vuoto — ID `27597`.
2. Forte scossa di terremoto nel Fiorentino — ID `52481`.
3. Canale Monterano: esplosa una palazzina di due piani, 4 i feriti — ID `52816`.

Perché mostrarla: Digita terremoto e scegli Data più recente: i primi tre titoli cambiano, il totale resta 156.

Limiti: “Milano: deragliato treno vuoto” e l’esplosione a Canale Monterano menzionano il terremoto nel corpo: sono corrispondenze testuali, non classificazioni per evento. Le date possono essere date di modifica.

## Selezione consigliata e scaletta di cinque minuti

Le sei tappe migliori sono: `terremoto`, `elezione`/`elezioni`, `citta`/`città`, `"banca centrale"`,
`Roma + Milano`/`Roma | Milano`, `elezioni` con filtri. Le varianti di ogni tappa si eseguono dal vivo.

| Tempo | Operazione | Messaggio da spiegare |
|---|---|---|
| 0:00–0:35 | Homepage e ricerca `terremoto` | 12.209 documenti reali, ricerca su titolo e corpo, 156 corrispondenze e snippet evidenziati. |
| 0:35–1:10 | Pagina successiva, apri un articolo e torna ai risultati | Paginazione stabile, testo consultabile, termini evidenziati, fonte originale e attribuzione. |
| 1:10–1:55 | `elezione`, poi `elezioni`; `citta`, poi `città` | Stesso analyzer in indicizzazione e ricerca: 621 risultati per le flessioni, 1.207 per gli accenti. |
| 1:55–2:35 | `"banca centrale"` | 33 risultati; “Le banche centrali tagliano i tassi” illustra la differenza fra frase analizzata e sottostringa letterale. |
| 2:35–3:20 | `Roma + Milano`, poi `Roma | Milano` | 1.157 contro 3.292 risultati; i primi titoli possono restare uguali. Nel corpus ci sono anche riferimenti calcistici. |
| 3:20–4:15 | `elezioni -Roma`, poi `elezioni` con Italia, poi senza categoria e anno 2008 | 536, 303 e 117 risultati. I filtri sono esatti e si rimuovono dalle etichette visibili. |
| 4:15–5:00 | `terremoto` con Data più recente; apri `/health` o l’API | Stesso totale, ordine diverso; chiarire il fallback sulla data di modifica e la distinzione tra corrispondenza e pertinenza. |

Tenere lo smoke test già eseguito in un secondo terminale. Non avviare indicizzazione, test che modificano
indici o campagne di benchmark durante la presentazione. Se un servizio si ferma, mostrare il messaggio
di indisponibilità e ripristinare il servizio; non sostituire i risultati live con quelli di questa guida.

## Verifica automatica

Con Flask già avviato, in un secondo terminale:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -B -m pytest -q -m "not elasticsearch and not realdump"
.venv\Scripts\python.exe -B -m unittest discover -s experiments/llm-evaluation/tests -v
.venv\Scripts\python.exe -B scripts/demo_smoke.py --es-url http://127.0.0.1:9200 --index-name itwikinews_hw4_italiano --out .reproduction/demo/smoke.json
```

Lo smoke test verifica disponibilità, indice e analyzer, conteggio, `/health`, homepage e CSS, tutte le
12 query sia direttamente sia via API, top-3 misurati, filtri, date, token di stemming/accenti, relazione
di unione/intersezione AND/OR, esclusione NOT, paginazione, articolo, fonte e highlighting.
Usa soltanto chiamate di lettura verso Elasticsearch; non contiene operazioni di gestione degli indici.
`PASS` significa riuscito, `FAIL` fallito, `SKIP` non eseguibile per prerequisiti assenti. Exit code 0:
tutto riuscito; 1: almeno un fallimento; 2: soli controlli non eseguibili. Il confronto del conteggio
si può parametrizzare con `--expected-documents`, ma le aspettative delle query rimangono quelle del corpus
documentato. Per un altro corpus occorre un nuovo insieme di casi dichiarato, non risultati fittizi.

La verifica misurata ha prodotto **36 PASS, 0 FAIL, 0 SKIP**. I test offline e di integrità sono riepilogati
nel resoconto finale della preparazione. I report locali sono in `.reproduction/demo/`, ignorati da Git.
La suite con marker `elasticsearch`/`realdump` comprende creazione e cancellazione di indici di prova e
un test di latenza: non è stata eseguita in questa preparazione.

## Visualizzazione e screenshot

Aprire http://127.0.0.1:5000/ sul computer dove gira Flask. Per una verifica visiva ripetibile:

1. Desktop, larghezza circa 1440 px: homepage con conteggio e sei esempi cliccabili.
2. Cercare `terremoto`: salvare risultati, snippet evidenziati e faccette.
3. Aprire il primo articolo dalla ricerca: salvare termini evidenziati e fonte; verificare il ritorno alla pagina originaria.
4. In Firefox, **Ctrl+Shift+S** permette di salvare uno screenshot. Per la vista mobile usare **Ctrl+Shift+M**, larghezza 390 px; verificare che form e risultati non richiedano scorrimento orizzontale.
5. Provare la navigazione da tastiera: Tab, Invio, link “Vai al contenuto”, guida sintassi, filtri e paginazione.

Il CSS include layout per schermi piccoli e indicatori di focus; le pagine non richiedono JavaScript,
font remoti o framework frontend. La verifica visiva automatizzata non è stata possibile in questa
sessione: sia il connettore Firefox sia l’host dell’altro accesso browser erano indisponibili. Sono stati
verificati HTML e API live; non si dichiara una verifica visiva desktop/mobile e non si allegano screenshot simulati.

## Attribuzioni, limiti e diagnosi

Il vecchio footer che assegnava CC BY 2.5 a tutti i testi è stato rimosso. L’indice esistente non conserva
la licenza per articolo: l’interfaccia rimanda a fonte, crediti e cronologia, senza inventare una licenza
unica. Le licenze registrate nel dump possono differire dalle indicazioni attuali del sito; per la
provenienza scientifica vedere [LICENSING.md](experiments/llm-evaluation/LICENSING.md).

- Indice mancante: il launcher si interrompe, senza indicizzare; scegliere un indice italiano esistente o preparare esplicitamente il corpus in una sessione separata.
- Porta occupata: fermare il precedente server oppure usare `-Port` e `--base-url` coerenti.
- Elasticsearch assente: avviare Docker Desktop e il container. Durante una richiesta i guasti ES producono HTTP 503; `/health` e `/api/search` rispondono in JSON.
- Zero risultati: controllare operatori e filtri; i filtri attivi restano rimovibili anche con zero corrispondenze.
- Rilevanza: non sono disponibili giudizi umani; l’accordo tra LLM non prova correttezza. La demo è funzionale, non un nuovo benchmark.
- Paginazione: si conservano il limite di 10.000 risultati e lo spareggio `article_id`; per altri risultati restringere query e filtri. Nessuna fotografia immutabile durante scritture concorrenti.
- Highlighting: gli snippet e il testo evidenziato provengono dall’highlighter HTML di Elasticsearch; il fallback esegue escaping. Articoli molto lunghi possono avere evidenziazione parziale. Il testo consultabile è quello estratto dal parser, non l’HTML completo della pagina Wikimedia.

Nessun commit o push, nessuna nuova campagna prestazionale, nessuna ricostruzione di indici.
I file sotto `experiments/`, manifest, annotazioni, log e risultati scientifici sono rimasti invariati.
