"""Audit qualitativo dei giudizi LLM discordanti: NON adjudication e NON ground truth umana."""
from __future__ import annotations
import csv, json, hashlib, zipfile, collections, pathlib, statistics
import numpy as np

ROOT = pathlib.Path('/mnt/data')
SRC = ROOT / 'wikinews_confronto_GPT6_ClaudeOpus55'
OUT = ROOT / 'wikinews_audit_qualitativo_53_disaccordi'
OUT.mkdir(exist_ok=True)

# Categories name interpretation, not an authoritative correctness label.
A = 'Criterio 1/2 o ambiguita dell’intento'
G = 'Possibile sovrastima GPT-6'
C = 'Possibile sottostima Claude'
U = 'Possibile sottostima GPT-6'

# One row per distinct news title (the original data repeat some news for correlated query variants).
# Each entry: audit category + short factual rationale rooted in the document and written query intent.
manual = [
 (U, 'Necrologio ampio: include un riepilogo dettagliato di cariche, attivita e rapporti istituzionali; e piu di una menzione occasionale.'),
 (A, 'Le dichiarazioni di Storace sono il fulcro, ma riguardano il capo dello Stato e una vicenda che coinvolge Napolitano.'),
 (A, 'L’indagine giudiziaria concerne le offese al Presidente, che e parte centrale ma non protagonista attivo della notizia.'),
 (C, 'La candidatura e la competizione elettorale con Schroeder sono direttamente attivita politica di Merkel, anche se parla di sondaggi.'),
 (G, 'Il clima appare soltanto tra diversi temi elencati di un documentario sui giovani: l’intento climatico non e soddisfatto.'),
 (A, 'L’appello e interamente sul rischio climatico e invoca azioni politiche; resta ambiguo quanta informazione concreta sia necessaria per il grado 2.'),
 (A, 'La lavatrice a basso consumo e una misura pratica indirettamente collegata al clima: borderline fra 0 e 1.'),
 (G, 'Il cambiamento climatico e menzionato in premessa, ma l’articolo riguarda la campagna contro la caccia alle balene.'),
 (C, 'La protesta riguarda discriminazioni occupazionali, appalti e sciopero: temi diretti di condizioni e diritti dei lavoratori.'),
 (C, 'Lo sciopero dei lavoratori viene interrotto con la forza dall’esercito: e un caso diretto di diritti e condizioni di lavoro.'),
 (U, 'Il corpo descrive un infortunio mortale sul lavoro, assenza di protezioni, ispettori SPSAL e statistiche degli incidenti.'),
 (A, 'Notizia societaria ma i 162 posti a rischio sono anche nel titolo; 1 e 2 dipendono dal peso attribuito alla condizione lavorativa.'),
 (A, 'Aggressione legata a una maglietta politica di studente: cronaca ma anche liberta di espressione in ambito scolastico.'),
 (G, 'Tragedia con studente e contesto scolastico, ma senza evidenze nel testo relative a diritti, condizioni o iniziative degli studenti.'),
 (A, 'Il bullismo scolastico e le minacce fra compagni riguardano condizioni di sicurezza, ma la notizia e presentata come cronaca giudiziaria.'),
 (G, 'Episodio di aggressione e sanzione individuale: non sviluppa condizioni, diritti o iniziative degli studenti; il 2 e troppo ampio.'),
 (C, 'Il testo racconta una manifestazione organizzata soprattutto da studenti e gli scontri: iniziativa studentesca esplicita nell’intento.'),
 (G, 'Incidente stradale durante una gita: essere studenti e circostanza, non l’oggetto informativo della notizia.'),
 (A, 'Violenza in una scuola; puo soddisfare una ricerca sulla sicurezza degli studenti, oppure essere mera cronaca episodica.'),
 (G, 'Comportamento individuale punito in una classe, senza contenuti sostanziali su politiche, condizioni o iniziative studentesche.'),
 (A, 'Sospensione di una docente per paragone espresso da studenti: tema di espressione e scuola, ma il focus e il provvedimento sulla docente.'),
 (A, 'Multa per ripresa video a scuola e privacy: evento individuale ma riguarda l’applicazione di una regola normativa agli studenti.'),
 (A, 'Aggressione fra compagni in classe: sicurezza scolastica tangente, ma il focus e sul fatto di cronaca.'),
 (C, 'Imposizione normativa del taglio di capelli agli studenti: riguarda direttamente condizioni e liberta personali degli studenti.'),
 (G, 'La conferenza di Stallman e la provocazione dei ninja si svolgono a Yale: l’universita e un luogo, non il tema istituzionale.'),
 (G, 'L’UNITRE e associazione culturale di terza eta; l’intervista verte sul contenzioso personale del fondatore, non su politiche accademiche.'),
 (C, 'Il testo completo parla di missioni ISS, equipaggi, moduli, ricerca, astronauti e attivita a bordo, non soltanto di una conferenza.'),
 (A, 'Il necrologio riassume la carriera calcistica e le squadre, ma non riguarda una competizione o un risultato attuale.'),
 (A, 'Le intercettazioni di Calciopoli riguardano il mondo del calcio, ma il fulcro e l’indagine, non competizioni e risultati.'),
 (A, 'Indagini su Calciopoli: connessione con squadre e campionati forte, ma notizia giudiziaria.'),
 (A, 'Il dibattimento del processo sportivo influenza potenzialmente i campionati; l’articolo non tratta risultati in campo.'),
 (A, 'Interrogatorio giudiziario di Moggi, solo indirettamente relativo all’organizzazione del campionato.'),
 (A, 'Panoramica dello scandalo calcio, con ripercussioni sportive ma focus principale sulle indagini.'),
 (A, 'Cambio degli indici di Piazza Affari: informazione di mercato strutturale, non andamento dei prezzi; interpretazione dipende dallo scope.'),
 (C, 'Il testo e direttamente sull’andamento delle azioni FIAT e sui volumi scambiati: singolo titolo comunque azionario.'),
 (C, 'Il testo descrive l’aumento del 9% di Northern Rock e le cause finanziarie; andamento azionario diretto se ammessi singoli titoli.'),
 (A, 'Nuova quotazione Parmalat: mercato azionario ma soprattutto storia societaria e creditori.'),
 (A, 'Fusione Intesa-Sanpaolo e debutto in Borsa, con alcune quotazioni: parte diretta e parte societaria.'),
 (A, 'Sospensione delle negoziazioni di singoli titoli: rilevante per il mercato, ma non per l’andamento generale dei prezzi.'),
 (A, 'Trasferimento della quotazione FIAT da Milano a Wall Street: mercato azionario, ma non andamento del mercato.'),
 (C, 'L’articolo documenta esplicitamente la perdita di valore di Apple in Borsa: andamento di un titolo azionario.'),
 (A, 'Acquisizione di Borsa Italiana da London Stock Exchange: assetto societario dell’infrastruttura, non andamento azionario.'),
]

with (SRC / '53_disagreements_to_review.csv').open(encoding='utf-8-sig', newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==53
with zipfile.ZipFile(ROOT / 'blind_assessor_package.zip') as z:
    candidates=[json.loads(x) for x in z.read('blind_candidates.jsonl').decode('utf-8').splitlines()]
    intent_list=json.loads(z.read('validation_queries.json').decode('utf-8'))
cand={(a['query_id'],a['candidate_id']):a for a in candidates}
intents={a['id']:a['intent'] for a in intent_list}
titles=list(dict.fromkeys(x['title'] for x in rows))
assert len(titles)==42 and len(manual)==42
notes={title: manual[i] for i,title in enumerate(titles)}

outrows=[]
for r in rows:
    assert (r['query_id'],r['candidate_id']) in cand
    case=cand[(r['query_id'],r['candidate_id'])]
    assert case['title']==r['title']
    cat,note=notes[r['title']]
    outrows.append({
        'query_id':r['query_id'],
        'query':r['query'],
        'intento_ufficiale':intents[r['query_id']],
        'candidate_id':r['candidate_id'],
        'titolo':r['title'],
        'grado_GPT6':r['gpt6_grade'],
        'grado_Claude':r['claude_grade'],
        'categoria_diagnostica':cat,
        'motivazione_qualitativa':note,
        'nota_originale_GPT6':r['gpt6_note'],
        'nota_originale_Claude':r['claude_note'],
        'url':r['url'],
        'text_length':len(case['body']),
        'text_sha256':hashlib.sha256(case['body'].encode('utf-8')).hexdigest(),
    })
fields=list(outrows[0]);p=OUT/'audit_53_casi.csv'
with p.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(outrows)

counts=collections.Counter(r['categoria_diagnostica'] for r in outrows)
unique_counts=collections.Counter(notes[t][0] for t in titles)
print('PAIR CAUSES',counts, 'UNIQUE ARTICLE CAUSES',unique_counts)

# Load existing per-query paired metric differences; do not recompute qrels or replace any judge.
contrast_rows=list(csv.DictReader((SRC/'ranking_contrasts_by_query.csv').open(encoding='utf-8-sig')))
judges=sorted({r['judge'] for r in contrast_rows})
loo=[];boot=[]
for judge in judges:
 for contrast in ('B-A','C-B'):
  r=[x for x in contrast_rows if x['judge']==judge and x['contrast']==contrast]
  groups=list(dict.fromkeys(x['group'] for x in r))
  mean=sum(float(x['nDCG@10']) for x in r)/len(r)
  for group in groups:
   sub=[float(x['nDCG@10']) for x in r if x['group']!=group]
   loo.append({'giudice':judge,'contrasto':contrast,'gruppo_escluso':group,'n_query_rimanenti':len(sub),'delta_ndcg_rimanente':sum(sub)/len(sub),'delta_completo':mean})
  noacc=[x for x in r if x['group']!='accenti_0']
  ng=list(dict.fromkeys(x['group'] for x in noacc))
  by={g:np.array([float(x['nDCG@10']) for x in noacc if x['group']==g]) for g in ng}
  rng=np.random.default_rng(20261118)
  reps=[]
  for _ in range(10000):
   sampled=rng.choice(ng,size=len(ng),replace=True)
   values=np.concatenate([by[g] for g in sampled])
   reps.append(values.mean())
  m=sum(float(x['nDCG@10']) for x in noacc)/len(noacc)
  low,high=np.quantile(reps,[0.025,0.975])
  boot.append({'giudice':judge,'contrasto':contrast,'esperimento':'escluso gruppo accenti_0 (v12/v13)','query_rimanenti':len(noacc),'gruppi_rimanenti':len(ng),'delta_ndcg':m,'bootstrap_IC95_basso':low,'bootstrap_IC95_alto':high,'B_10000':'seed=20261118'})
for name,items in [('leave_one_group_out.csv',loo),('bootstrap_senza_accenti.csv',boot)]:
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)

# Aggregate material for Markdown report
counts_md='\n'.join(f'| {k} | {v} | {unique_counts[k]} |' for k,v in counts.most_common())
q_counts=collections.Counter(r['query_id'] for r in rows)
q_titles={v['id']:v['query'] for v in intent_list}
q_md='\n'.join(f'| {qid} · {q_titles[qid]} | {n} |' for qid,n in sorted(q_counts.items()))
loomin={}
for judge in judges:
 for contrast in ('B-A','C-B'):
  sub=[r for r in loo if r['giudice']==judge and r['contrasto']==contrast]
  loomin[judge,contrast]=(min(r['delta_ndcg_rimanente'] for r in sub),max(r['delta_ndcg_rimanente'] for r in sub))

md=f'''# Revisione qualitativa dei 53 disaccordi GPT-6 / Claude Opus 5.5

**Natura dell'analisi:** audit qualitativo *esplorativo*, basato sul testo degli articoli e sugli intenti delle 18 query. **Non si creano nuovi giudizi di rilevanza** e non si sostituiscono i CSV dei due modelli. Le categorie sono valutazioni metodologiche dell'analista, non etichette di ground truth né decisioni di adjudication umana.

## Perimetro e integrità

- Input: `blind_assessor_package.zip/blind_candidates.jsonl`, `validation_queries.json`, `53_disagreements_to_review.csv`.
- 53 coppie discordanti su 244; 42 articoli distinti (11 titoli ricorrono nelle query morfologicamente accoppiate).
- Tutti i 53 ID opachi corrispondono a un candidato nel pacchetto cieco; i testi originali sono identificabili tramite SHA256 delle rispettive righe dell'audit.
- I giudizi originali, le motivazioni e gli URL sono preservati in `audit_53_casi.csv`.

## Tipologie diagnostiche

| Categoria | Coppie | Articoli distinti |
|---|---:|---:|
{counts_md}

Queste categorie indicano soltanto la lettura metodologicamente piu convincente del documento in relazione all'intento, non quale giudice sia certamente "corretto". Un unico articolo puo comparire in query diverse ma equivalenti.

### Dinamica dei disaccordi

- GPT-6 2 → Claude 1: **37** coppie (soglia per attribuire rilevanza diretta).
- GPT-6 1 → Claude 0: **10** coppie (menzione marginale del tema).
- GPT-6 2 → Claude 0: **4** coppie (studenti e singoli episodi disciplinari, in due articoli ripetuti).
- GPT-6 1 → Claude 2: **2** coppie (necrologio istituzionale di Napolitano e incidente mortale sul lavoro a Taranto).

## Disaccordi per query

| Query | Disaccordi |
|---|---:|
{q_md}

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
| GPT-6 | B−A | {loomin['GPT-6','B-A'][0]:+.4f} | {loomin['GPT-6','B-A'][1]:+.4f} |
| Claude Opus 5.5 | B−A | {loomin['Claude-Opus-5.5','B-A'][0]:+.4f} | {loomin['Claude-Opus-5.5','B-A'][1]:+.4f} |
| GPT-6 | C−B | {loomin['GPT-6','C-B'][0]:+.4f} | {loomin['GPT-6','C-B'][1]:+.4f} |
| Claude Opus 5.5 | C−B | {loomin['Claude-Opus-5.5','C-B'][0]:+.4f} | {loomin['Claude-Opus-5.5','C-B'][1]:+.4f} |

La direzione dei contrasti resta invariata escludendo a turno uno dei 15 gruppi. **Questo non equivale a significativita statistica**, perche le query non sono un campione probabilistico di log utenti.

### Sensibilita all'effetto delle query sugli accenti

L'effetto B−A e in parte alimentato da `universita` (senza accento); rimuovere il gruppo `accenti_0` lascia 16 query in 14 gruppi:

| Giudice | B−A senza accenti | IC95 bootstrap per gruppi |
|---|---:|---|
| GPT-6 | {next(x for x in boot if x['giudice']=='GPT-6' and x['contrasto']=='B-A')['delta_ndcg']:+.4f} | [{next(x for x in boot if x['giudice']=='GPT-6' and x['contrasto']=='B-A')['bootstrap_IC95_basso']:+.4f}; {next(x for x in boot if x['giudice']=='GPT-6' and x['contrasto']=='B-A')['bootstrap_IC95_alto']:+.4f}] |
| Claude Opus 5.5 | {next(x for x in boot if x['giudice']=='Claude-Opus-5.5' and x['contrasto']=='B-A')['delta_ndcg']:+.4f} | [{next(x for x in boot if x['giudice']=='Claude-Opus-5.5' and x['contrasto']=='B-A')['bootstrap_IC95_basso']:+.4f}; {next(x for x in boot if x['giudice']=='Claude-Opus-5.5' and x['contrasto']=='B-A')['bootstrap_IC95_alto']:+.4f}] |

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
'''
(OUT/'REPORT_AUDIT_53.md').write_text(md,encoding='utf-8')
(OUT/'README.md').write_text('Audit qualitativo esplorativo dei disaccordi tra due annotatori LLM. Il report non modifica le qrels e non aggiunge giudizi umani. Consultare REPORT_AUDIT_53.md.\n',encoding='utf-8')

# Include the audit-generating script for disclosure and reproducibility.
import shutil
shutil.copy2(__file__,OUT/'build_llm_disagreement_audit.py')
archive=ROOT/'wikinews_audit_qualitativo_53_disaccordi.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for file in OUT.iterdir():
  if file.is_file():z.write(file,arcname=file.name)
print('OUT',archive,archive.stat().st_size)
print('Report',OUT/'REPORT_AUDIT_53.md')
