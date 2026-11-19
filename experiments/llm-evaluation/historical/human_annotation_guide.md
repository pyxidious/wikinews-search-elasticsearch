# Istruzioni per la valutazione umana cieca

Il campione contiene 18 query sintetiche deliberate e intenti fissati prima di osservare le graduatorie. Non deriva da log utenti. Consegnare ai valutatori solo `blind_assessor_package.zip`; conservare separatamente `ranking_private.json`, misure e rapporto finché entrambi hanno terminato.

Due valutatori devono lavorare indipendentemente, senza consultarsi, senza vedere configurazione, posizione o punteggio e senza usare etichette generate da AI. Aprire `blind_annotation.html`, inserire un identificativo personale, leggere intento e testo e assegnare un grado. In alternativa compilare il proprio template CSV usando `blind_candidates.jsonl`. Nessuna etichetta è preselezionata. Il salvataggio locale del browser non sostituisce l'esportazione: esportare e conservare il CSV. Usare profili/browser separati per i due valutatori.

Scala ordinale:

- **0 — non pertinente:** il documento non soddisfa l'intento; una citazione incidentale non basta.
- **1 — parzialmente pertinente:** contiene informazioni utili ma affronta solo un aspetto secondario o incompleto dell'intento.
- **2 — direttamente pertinente:** il tema centrale risponde all'intento con informazioni sostanziali.

Giudicare il contenuto storico nel corpus, non l'attualità rispetto a oggi. Per ambiguità lessicali seguire l'intento esplicito. Per query tra virgolette valutare la rilevanza informativa, senza attribuire automaticamente un grado per la sola corrispondenza letterale. Segnalare difficoltà e contenuto illeggibile nelle note; non inventare giudizi. Non lasciare celle vuote se il documento è giudicabile; se non lo è, richiedere una decisione metodologica prima dell'analisi.

Congelare entrambi i CSV indipendenti prima di discutere divergenze. Calcolare prima accordo esatto e kappa di Cohen pesato quadratico (primario per l'accordo), con pesatura lineare di sensibilità. Successivamente un essere umano può produrre un terzo CSV adjudicato, completo. Lo strumento non assegna automaticamente giudizi né fa medie dei gradi.

Eseguire dal Python dell'ambiente originale (sostituire i percorsi):

```powershell
<repo>\.venv\Scripts\python.exe -B <risultati>\ranking_analysis.py --assessor1 <valutatore1.csv> --assessor2 <valutatore2.csv> --human-confirmed
```

Con `--adjudicated <consenso.csv>` si aggiunge l'analisi dopo consenso umano. `--human-confirmed` è una dichiarazione dell'operatore sulla provenienza, non un controllo automatico dell'identità o dell'indipendenza. Etichette AI-assisted non soddisfano tale dichiarazione e possono essere analizzate solo come esplorative con strumenti separati.

nDCG@10 è primaria: guadagno `2^grado - 1`, sconto `log2(posizione+1)`, ideale sui documenti giudicati del pool. P@5 (denominatore sempre 5) e MRR@10 sono secondarie; rilevante significa grado maggiore di zero. Per query senza documenti pertinenti nel pool, nDCG=0 per convenzione, il caso è segnalato ed è riportata anche la media che lo esclude. Questo non dimostra assenza di documenti pertinenti fuori dal pool. La profondità è 10 per ciascuna configurazione; duplicati rimossi per ID all'interno di ciascuna query.

Gli intervalli al 95% usano 10.000 bootstrap appaiati sui gruppi prefissati: lavoratore/lavoratori, studente/studenti e università/universita condividono un gruppo; le altre query sono singole. La stima rimane una media per query, il ricampionamento è per gruppo. Sono riportati B−A, C−B per query e vittorie/parità/sconfitte, senza conclusioni fondate solo sulla media. Gli IC non sono corretti per confronti multipli; non equivalgono automaticamente a significatività confermativa.

L'ampliamento va preregistrato in un nuovo workload prima di vedere ranking o giudizi aggiuntivi, con nuovi ID, intenti, categorie e gruppi. Non selezionare nuove query in funzione degli effetti già osservati.
