# Provenienza delle annotazioni: registrato e mancante

Consolidamento: **19 novembre 2026**. Questa è la data della verifica, non la data dell'annotazione.
Fonti complete e checksum dei membri degli ZIP: [SOURCE_ARCHIVES.json](SOURCE_ARCHIVES.json).
Le date ZIP sono metadati di confezionamento senza fuso dichiarato; non provano le date delle esecuzioni.

| Campo | GPT-6 | Claude Opus 5.5 |
|---|---|---|
| Provider riferito | OpenAI | Anthropic |
| Nome riferito | GPT-6 | Claude Opus 5.5 |
| Identificativo API esatto | non disponibile; non si inventa `gpt-6` | `claude-opus-5-5`, fornito dall'utente; payload API non disponibile |
| Revisione/snapshot effettivamente servito | non registrato | non registrato |
| Modalità di ragionamento | non registrato | High, secondo utente e README storico |
| Data annotazione | non registrata | non registrata |
| Prompt originale, inclusi messaggi di sistema | non disponibile | non disponibile |
| Temperature, top_p, seed LLM, limiti token | non registrati | non registrati |
| Strumenti, numero chiamate, batch, retry | non registrati; protocollo parla di sessione/passata unica | non registrati |
| Testo letto | titolo/testo disponibile, lettura mirata di alcuni lunghi secondo protocollo | titolo, inizio e passaggi pertinenti di alcuni lunghi, secondo resoconto |
| Porzioni lette per documento | non registrate | non registrate |
| Validazione umana | assente | assente |

La rubrica 0/1/2, gli intenti e il protocollo di cecità sono documentati, ma **non equivalgono al prompt
effettivamente trasmesso**. Non sono disponibili trascrizioni, richieste/risposte API o log di accesso ai testi.
Per il primo giudice si conservano protocollo, metadata e audit delle motivazioni/confidenza originali;
per il secondo le note sono quelle del CSV originale, comprese le celle vuote.

Input dichiarati: `blind_candidates.jsonl` e `validation_queries.json` dal benchmark, con hash registrati.
Il mapping privato è dichiarato usato dopo l'etichettatura per associare i risultati; l'effettiva separazione
non è verificabile da log. `PROMPT_PROVENANCE.json` riporta hash, prove disponibili e limiti per ciascun campo.
Il seed **20261118 è statistico**, non un seed delle chiamate LLM.

Non esiste qui un prompt ricostruito presentato come storico. Il calcolo delle metriche è verificabile;
la generazione delle etichette storiche **non è completamente replicabile**. Una nuova chiamata agli stessi
nomi commerciali può usare snapshot diversi o dare giudizi differenti anche con un prompt registrato.
