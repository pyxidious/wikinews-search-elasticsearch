# Revisione qualitativa dei 53 disaccordi GPT-6 / Claude Opus 5.5

**Natura dell'analisi:** audit qualitativo *esplorativo*, basato sul testo degli articoli e sugli intenti delle 18 query. **Non si creano nuovi giudizi di rilevanza** e non si sostituiscono i CSV dei due modelli. Le categorie sono valutazioni metodologiche dell'analista, non etichette di ground truth né decisioni di adjudication umana.

## Perimetro e integrità

- Input: `blind_assessor_package.zip/blind_candidates.jsonl`, `validation_queries.json`, `53_disagreements_to_review.csv`.
- 53 coppie discordanti su 244; 42 articoli distinti (11 titoli ricorrono nelle query morfologicamente accoppiate).
- Tutti i 53 ID opachi corrispondono a un candidato nel pacchetto cieco; i testi originali sono identificabili tramite SHA256 delle rispettive righe dell'audit.
- I giudizi originali, le motivazioni e gli URL sono preservati in `audit_53_casi.csv`.

## Tipologie diagnostiche

| Categoria | Coppie | Articoli distinti |
|---|---:|---:|
| Criterio 1/2 o ambiguita dell’intento | 26 | 23 |
| Possibile sovrastima GPT-6 | 13 | 8 |
| Possibile sottostima Claude | 12 | 9 |
| Possibile sottostima GPT-6 | 2 | 2 |

Queste categorie indicano soltanto la lettura metodologicamente piu convincente del documento in relazione all'intento, non quale giudice sia certamente "corretto". Un unico articolo puo comparire in query diverse ma equivalenti.

### Dinamica dei disaccordi

- GPT-6 2 → Claude 1: **37** coppie (soglia per attribuire rilevanza diretta).
- GPT-6 1 → Claude 0: **10** coppie (menzione marginale del tema).
- GPT-6 2 → Claude 0: **4** coppie (studenti e singoli episodi disciplinari, in due articoli ripetuti).
- GPT-6 1 → Claude 2: **2** coppie (necrologio istituzionale di Napolitano e incidente mortale sul lavoro a Taranto).

## Disaccordi per query

| Query | Disaccordi |
|---|---:|
| v01 · Giorgio Napolitano | 3 |
| v02 · Angela Merkel | 1 |
| v07 · cambiamento climatico | 4 |
| v08 · lavoratore | 4 |
| v09 · lavoratori | 3 |
| v10 · studente | 11 |
| v11 · studenti | 7 |
| v12 · università | 2 |
| v13 · universita | 2 |
| v15 · "stazione spaziale" | 1 |
| v16 · calcio | 6 |
| v18 · borsa | 9 |

## Casi decisivi letti nel testo

1. **`studente`/`studenti`, Vimercate e Pavia (GPT 2, Claude 0):** aggressione alla docente con sospensione, oppure spogliarelli in classe. L'intento verte su condizioni, diritti e iniziative studentesche: classificare come direttamente pertinente qualunque episodio avvenuto a uno studente e troppo permissivo. Il dubbio residuo fra 0 e 1 non giustifica automaticamente 2.
2. **`universita`/`università`, Stallman/Yale e UNITRE (GPT 1, Claude 0):** Yale e il luogo di una conferenza/provocazione; UNITRE e un'associazione culturale citata in un'intervista su vicende del fondatore. Non sono notizie su didattica universitaria, istituzioni accademiche o politiche di ricerca. Questo spiega la preferenza diagnostica per la lettura piu restrittiva.
3. **`lavoratore`, morti a Taranto (GPT 1, Claude 2):** l'articolo descrive incidenti mortali, protezioni mancanti, ispezioni SPSAL e statistiche sulle morti sul lavoro. Corrisponde direttamente al tema sicurezza sul lavoro: la classificazione 1 appare troppo prudente.
4. **`lavoratore`/`lavoratori`, sciopero in Ecuador (GPT 2, Claude 1):** l'esercito interrompe con la forza uno sciopero; diritti e condizioni lavorative sono centrali, anche se la notizia menziona l'estrazione del petrolio.
5. **`studente`/`studenti`, contestazione a Berlusconi (GPT 2, Claude 1):** la manifestazione e guidata principalmente da studenti; l'intento include espressamente le loro *iniziative*. Il criterio di Claude potrebbe aver ristretto eccessivamente il significato di iniziativa studentesca.
6. **`stazione spaziale`, incontro Guidoni (GPT 2, Claude 1):** il documento integrale non si limita alla divulgazione; contiene missioni ISS, equipaggi, moduli, attivita e ricerca a bordo. E un probabile caso di sottostima di Claude; non si puo pero dimostrare che derivi dalla lettura selettiva da lui dichiarata.
7. **`borsa`, variazioni di FIAT/Apple/Northern Rock (GPT 2, Claude 1):** le quotazioni di singoli titoli sono comunque andamento azionario. Se l'intento include singole azioni, 2 e difendibile; se riguarda soltanto indici aggregati, 1 e difendibile. La rubrica non specificava questa esclusione, dunque la restrizione di Claude rischia di essere troppo forte.
8. **`calcio`, Calciopoli (GPT 2, Claude 1):** notizie su intercettazioni e processi hanno forte relazione col calcio, ma affrontano soprattutto vicende giudiziarie invece che gare e risultati. La graduazione dipende da come si considera l'impatto dei procedimenti sulle competizioni.
9. **`cambiamento climatico`, documentario Generazione Z / balene (GPT 1, Claude 0):** il clima e menzionato incidentalmente; e discutibile attribuirgli rilevanza anche parziale rispetto a cause, conseguenze o politiche climatiche.
10. **`Giorgio Napolitano`, necrologio (GPT 1, Claude 2):** l'articolo presenta un resoconto ampio di cariche e relazioni politiche. Non e solamente un annuncio di morte; il grado 2 e plausibile.

## Robustezza del ranking ai disaccordi

I due giudici, considerati *separatamente*, hanno entrambi **B come configurazione con nDCG@10 media piu alta**. Non e confermato un ordinamento stabile fra A e C, molto vicine fra loro. Questa analisi **non modifica le loro qrels**.

### Lascia-fuori-un-gruppo (15 gruppi, effetti nDCG@10)

| Giudice | Contrasto | Min delta dopo esclusione | Max delta dopo esclusione |
|---|---|---:|---:|
| GPT-6 | B−A | +0.0444 | +0.0854 |
| Claude Opus 5.5 | B−A | +0.0436 | +0.0793 |
| GPT-6 | C−B | -0.0769 | -0.0133 |
| Claude Opus 5.5 | C−B | -0.0892 | -0.0177 |

La direzione dei contrasti resta invariata escludendo a turno uno dei 15 gruppi. **Questo non equivale a significativita statistica**, perche le query non sono un campione probabilistico di log utenti.

### Sensibilita all'effetto delle query sugli accenti

L'effetto B−A e in parte alimentato da `universita` (senza accento); rimuovere il gruppo `accenti_0` lascia 16 query in 14 gruppi:

| Giudice | B−A senza accenti | IC95 bootstrap per gruppi |
|---|---:|---|
| GPT-6 | +0.0444 | [-0.0010; +0.0949] |
| Claude Opus 5.5 | +0.0436 | [+0.0133; +0.0753] |

I bootstrap sono **esplorativi e post-hoc** e utilizzano 10.000 repliche con seed 20261118; non correggono gli errori sistematici dei due valutatori, ne consentono un'affermazione generale su tutte le possibili query.

## Considerazioni metodologiche

1. **Non effettuare adjudication implicita.** L'audit diagnostico non cambia i giudizi e non deve essere conteggiato come terzo valutatore indipendente; gli analisti conoscono gia i disaccordi.
2. **La rubrica originaria e troppo generica per 1 vs 2.** Esplicitare se per `borsa` sono inclusi i singoli titoli; se per `studente` siano pertinenti singoli episodi di cronaca; se per `calcio` siano incluse controversie giudiziarie. Questi dettagli dipendono dagli intenti predefiniti e possono essere raffinati solo per nuove prove dichiarate esplorative, senza selezionare ad hoc i casi che favoriscono A/B/C.
3. **Non fondere le etichette dei due LLM con media o voto di maggioranza** (due giudici non consentono un majority vote). Riportare metriche separate e accordo.
4. **Rilevanza non implica accuratezza fattuale dell'articolo.** La qualita enciclopedica o l'attendibilita della fonte non e stata valutata qui.
5. **Un bias puo essere condiviso.** L'accordo fra due LLM, anche se elevato, non prova la correttezza delle etichette.
6. **Query sintetiche e pooling top-10:** le conclusioni riguardano la popolazione operativa definita dall'esperimento, senza estimare recall sull'intero dump.

## File

- `audit_53_casi.csv`: ogni disaccordo originale, categoria metodologica e motivazione; include URL, intento, ID opaco, note, e hash del testo.
- `leave_one_group_out.csv`: effetto appaiato nDCG@10 eliminando a turno ciascun gruppo predefinito.
- `bootstrap_senza_accenti.csv`: nuova analisi di sensibilita escludendo il gruppo di accenti.
- `README.md`: istruzioni e chiarimento sul carattere non adjudicativo.
