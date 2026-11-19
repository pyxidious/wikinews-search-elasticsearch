# Testi, licenze e attribuzione

Verifica del 19 novembre 2026 sul dump storico con SHA-256 in `data/corpus_reference.json`:
sono stati rintracciati tutti i **210 articoli distinti** delle 244 coppie. I loro campi `license` riportano
**CC-BY-SA-4.0**; dati, URL di attribuzione e metadati di versione sono conservati in `data/article_licenses.json`.
Questo risultato riguarda gli articoli del pool, non una licenza unica inferita per tutto il dump.

La [pagina copyright corrente di Wikinotizie](https://it.wikinews.org/wiki/Wikinotizie:Copyright)
rimanda a CC BY 4.0 e spiega l'attribuzione tramite link all'articolo; i
[Termini Wikimedia, §7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content)
richiedono di rispettare la licenza applicabile e le eventuali eccezioni di progetto.
La [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) ha anche condizioni sulle modifiche.
Non si sostituisce retroattivamente il campo del dump con il testo di una pagina corrente e non si estende
la licenza dei testi a immagini o altri contenuti incorporati.

La pubblicazione curata **omette i corpi integrali e l'HTML**, sia nel repository sia nell'archivio prestazionale
predisposto. Conserva titoli, link, identificativi, lunghezze e hash, oltre alle annotazioni/motivazioni originali.
I link e i metadati consentono attribuzione e controllo della provenienza. Nessuna licenza generale degli
articoli viene attribuita automaticamente alle etichette LLM o al codice del progetto.

`reconstruct_candidates.py` ricostruisce localmente il testo effettivamente fornito, con lo stesso parser e il
dump ufficiale congelato, e rifiuta contenuti/hash differenti. Non basta riscaricare le pagine correnti.
Il ricalcolo delle metriche **non richiede i testi** né il download del dump. L'originale `results.zip`, che
include testi e vecchi materiali umani, resta sorgente locale immutata e non è indicato come asset da pubblicare.
