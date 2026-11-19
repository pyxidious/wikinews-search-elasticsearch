# Protocollo definitivo AI-only

Questa guida sostituisce, per lo studio consolidato, il piano di annotazione umana del 18 novembre.
Le etichette sono di **GPT-6 (OpenAI)** e **Claude Opus 5.5 (Anthropic, identificativo riferito
`claude-opus-5-5`, modalità High)**. Nessun essere umano ha annotato o convalidato queste qrels.
Non utilizzare il termine human-confirmed, neppure per l'audit qualitativo dei disaccordi.

Le 18 query e gli intenti sono congelati in `data/queries.json`; il pool è l'unione deduplicata per query
dei primi 10 risultati A/B/C: 244 coppie, 210 articoli distinti. `data/pool.metadata.jsonl` mantiene ID ciechi,
titolo, URL e hash del testo; `data/ranking_private.json` contiene mapping agli ID Elasticsearch e i medesimi
ranking per entrambi i giudici. Il corpo è ricostruibile dal dump, non ridistribuito qui.

Scala registrata nel protocollo GPT-6 e adottata nel benchmark:

- **0:** non pertinente al bisogno informativo; una coincidenza lessicale non basta.
- **1:** pertinente parzialmente, come aspetto secondario o contestuale.
- **2:** il tema centrale soddisfa direttamente l'intento.

La cecità rispetto a rango, punteggio e configurazione e l'assenza delle qrels GPT-6 nell'input Claude
sono **dichiarate nei materiali e nel resoconto fornito**, non verificate mediante log delle conversazioni.
I giudizi non vengono fusi o mediati. L'indipendenza dichiarata di due sessioni/modelli non garantisce
indipendenza dei bias o dei dati di addestramento.

Claude ha dichiarato lettura selettiva di alcuni articoli lunghi: titolo, introduzione e passaggi pertinenti.
Anche il protocollo storico GPT-6 menziona lettura mirata per alcuni testi lunghi. Non sono registrati
gli articoli interessati, gli intervalli di caratteri letti, gli strumenti, i batch o i conteggi delle chiamate.
Un file di input contenente il testo integrale non prova che quel testo sia stato letto integralmente.

`data/qrels_gpt6.original.csv` e `data/qrels_claude.original.csv` sono copie byte per byte, complete,
non template. I nomi nel campo `assessor` sono conservati: `GPT-6-LLM-only` e `LLM-SECOND-JUDGE`.
Quest'ultima etichetta generica non identifica da sola il modello: l'associazione a Claude proviene
dal resoconto del valutatore/utente e dalla documentazione del confronto.

L'audit dei 53 disaccordi è esplorativo e successivo: categorie e motivazioni sono conservate, non
ricalcolate come nuova semantica, non modificano i gradi e non valgono come terzo giudice o adjudication umana.
L'accordo esatto e il kappa misurano concordanza, non accuratezza. I bootstrap non incorporano errore
sistematico degli LLM, ambiguità della rubrica, lettura parziale o spostamento a query reali.

Il testo originale dei prompt non è presente negli archivi. Le rubriche e i rapporti storici non sono
spacciati per messaggi originali: vedere [PROMPT_PROVENANCE.md](PROMPT_PROVENANCE.md) e il file JSON omonimo.
Non viene inventato un prompt retroattivo. Una futura riannotazione dovrà registrare un nuovo prompt,
il modello effettivamente servito e tutti i parametri, e restare distinta da queste qrels.

Lo script `historical/human_ranking_analysis.py` conserva intatto il requisito `--human-confirmed`;
non è invocato per le etichette AI. `reproduce.py` usa esclusivamente il calcolatore AI storico e i CSV congelati.
