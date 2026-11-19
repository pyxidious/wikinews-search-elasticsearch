# Kit di riproducibilità, dati grezzi e distribuzione manuale

Il kit raccoglie i sorgenti e gli esperimenti descritti nell'[indice tecnico](README.md); l'asset dei dati
grezzi permette il ricalcolo delle statistiche prestazionali. Questa guida descrive verifica dei checksum,
preparazione locale e distribuzione manuale.

Directory permanente prevista per questa consegna:
`C:\Users\proti\Desktop\wikinews-benchmark-publication\`.
Nessun caricamento, commit, push, tag o merge è eseguito dagli strumenti di preparazione.

## File da distribuire

| File | Scopo |
|---|---|
| `wikinews-reproducibility-kit-20261119.zip` | Copia verificata dei sorgenti pubblicabili, due esperimenti, risultati, riferimenti, test e documentazione; codice applicativo originale invariato |
| `performance-raw-20261118.zip` | Le due misure grezze grandi, immutate, e il loro registro; nessun testo integrale |
| `SHA256SUMS` | SHA-256 effettivi dei due ZIP, calcolati dopo la costruzione |
| `RELEASE_MANIFEST.json` | Dimensioni, hash e stato locale della consegna |

Il raw ha SHA-256 **`464c3438507d53de3c4f430ea42b03271de3843ca667827afc5bd007d11f97c9`**,
dimensione **58.175.169 byte**. Contiene `search_raw.csv` (223.634.590 byte) e `telemetry.jsonl`
(30.870.892 byte), con hash originali in [RAW_DATA.json](performance-20261118/RAW_DATA.json).
L'hash del kit non è inserito nei suoi stessi sorgenti per evitare un riferimento circolare:
è nel file `SHA256SUMS` distribuito accanto al kit.

Non distribuire automaticamente gli ZIP in `reproducibility-inputs/`, l'originale `results.zip`,
dump, testi ricostruiti, vecchie copie di lavoro, ambienti Python o `.git/`. Non aggiungere i grandi
raw al normale versionamento. La regola `.gitignore` non rimuove eventuali file già versionati:
la selezione finale resta responsabilità del pubblicatore, senza che questo strumento usi Git.

## Preparazione locale ripetibile

Da un sorgente già verificato, scegliere sempre una **nuova** directory esterna:

```powershell
python -B experiments/prepare_publication.py --destination C:/path/nuova-consegna --raw-archive C:/path/performance-raw-20261118.zip
```

Lo strumento rifiuta destinazioni esistenti, archivi inattesi e file sorgente grandi; esclude lo staging,
crea `source-snapshot/`, copia in binario e sincronizza i file su disco, verifica ogni SHA prima di costruire
il kit e ne controlla tutte le entry/CRC. `source-snapshot/SOURCE_SHA256.json` contiene il registro completo.
Non ripara né sovrascrive copie precedenti e non contatta GitHub, Elasticsearch o modelli.

Per una sola nuova copia di verifica:

```powershell
python -B experiments/prepare_publication.py --snapshot-only --destination C:/path/nuova-copia-verifica
```

## Pubblicare: attività manuale dell'utente

1. Verificare che sorgenti e documentazione da pubblicare siano quelli della consegna finale.
2. Nell'interfaccia GitHub del repository aprire **Releases**, preparare una release/bozza e allegare i quattro
   file sopra. Scegliere tag e pubblicazione secondo il proprio processo; qui non sono creati automaticamente.
3. Copiare nelle note i checksum effettivi e specificare che le etichette sono AI-only, non validate da umani.
4. Dopo il caricamento annotare gli URL **reali** del kit e del raw. `RAW_DATA.json.download_url` è intenzionalmente
   `null` finché il raw non è pubblicato; se si aggiorna il JSON, rigenerare il relativo manifest e una nuova
   consegna, conservando la provenienza della precedente. Non inventare un URL di release.
5. Riscaricare gli asset e verificarli contro `SHA256SUMS`.

Il sorgente automatico ZIP/TAR che GitHub associa a un tag non sostituisce l'asset dei raw.
Riferimento: [gestione delle release GitHub](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Ricalcolo offline da kit e dati grezzi

Scaricare kit, raw e `SHA256SUMS` dalla release che il pubblicatore renderà disponibile.
Verificare prima gli hash, ad esempio in PowerShell:

```powershell
Get-FileHash ./wikinews-reproducibility-kit-20261119.zip -Algorithm SHA256
Get-FileHash ./performance-raw-20261118.zip -Algorithm SHA256
Expand-Archive ./wikinews-reproducibility-kit-20261119.zip -DestinationPath ./wikinews-reproduction
Set-Location ./wikinews-reproduction
python -m venv .reproduction/venv
$py = './.reproduction/venv/Scripts/python.exe'
& $py -m pip install -r experiments/llm-evaluation/requirements-reproduction.txt
& $py -B -m unittest discover -s experiments/llm-evaluation/tests -v
& $py -B experiments/llm-evaluation/reproduce.py --out .reproduction/llm
& $py -B experiments/performance-20261118/recompute.py --raw-archive ../performance-raw-20261118.zip --out .reproduction/performance
```

L'installazione delle dipendenze è una preparazione distinta; **i due calcoli successivi sono offline** e
non richiedono chiavi API, server o testi integrali. Su Linux/macOS usare `.reproduction/venv/bin/python`
al posto di `Scripts/python.exe` (la verifica locale è su Windows/Python 3.10.0).

Gli output `verification.json` devono indicare `passed: true`, senza discrepanze. Rilevanza: tolleranze
assoluta/relativa 1e-12; prestazioni: assoluta 1e-9 e relativa 1e-12. Le tabelle non sono input delle metriche:
sono confrontate soltanto dopo il ricalcolo. Rimangono i limiti storici documentati in
[PROMPT_PROVENANCE.md](llm-evaluation/PROMPT_PROVENANCE.md): prompt, snapshot e parametri LLM mancanti
non vengono recuperati da un ricalcolo riuscito. Nessuna validazione umana è implicita.
