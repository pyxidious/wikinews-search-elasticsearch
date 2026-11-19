param(
    [string]$IndexName = $env:ES_INDEX,
    [string]$EsUrl = $(if ($env:ES_URL) { $env:ES_URL } else { 'http://127.0.0.1:9200' }),
    [int]$Port = 5000,
    [switch]$SkipDocker,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $demoRoot
$demoPython = Join-Path $demoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    throw 'Creare prima .venv: py -3 -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt'
}
if ($Port -lt 1 -or $Port -gt 65535) { throw 'La porta deve essere compresa tra 1 e 65535.' }
$demoListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try { $demoListener.Start() }
catch { throw "Porta $Port occupata. Fermare il server precedente oppure scegliere -Port 5001." }
finally { $demoListener.Stop() }
if (-not $SkipDocker) {
    if ($EsUrl -notin @('http://127.0.0.1:9200', 'http://localhost:9200')) {
        throw 'Per un Elasticsearch esterno usare -SkipDocker e -EsUrl.'
    }
    & docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Avviare Docker Desktop e attendere che sia pronto, poi riprovare.' }
    & docker compose up -d --no-recreate elasticsearch
    if ($LASTEXITCODE -ne 0) { throw 'Avvio Elasticsearch non riuscito.' }
}
$demoPreflight = @'
import sys
from wikinews_search.indexer import make_client
es = make_client(sys.argv[1]).options(request_timeout=2, max_retries=0)
requested = '' if sys.argv[2] == '-' else sys.argv[2]
choices = [requested] if requested else ['itwikinews', 'itwikinews_hw4_italiano']
try:
    for name in choices:
        if es.indices.exists(index=name):
            fields = es.indices.get_mapping(index=name)[name]['mappings']['properties']
            if any(fields[f].get('analyzer') != 'italiano' for f in ('title','body')):
                sys.exit(5)
            print(name)
            sys.exit(0)
    sys.exit(3)
except Exception:
    sys.exit(4)
'@
$demoSelected = $null
$demoRequested = if ($IndexName) { $IndexName } else { '-' }
for ($demoAttempt = 0; $demoAttempt -lt 60; $demoAttempt++) {
    $demoOutput = & $demoPython -B -c $demoPreflight $EsUrl $demoRequested
    if ($LASTEXITCODE -eq 0) { $demoSelected = "$demoOutput".Trim(); break }
    if ($LASTEXITCODE -eq 3) {
        throw 'Indice assente. Nessun indice viene creato automaticamente. Vedere DEMO_GUIDE.md per la preparazione esplicita del corpus.'
    }
    if ($LASTEXITCODE -eq 5) { throw 'Analyzer non italiano. Scegliere un indice compatibile con -IndexName.' }
    Start-Sleep -Seconds 2
}
if (-not $demoSelected) { throw 'Elasticsearch non disponibile entro 120 secondi.' }
& $demoPython -B -m wikinews_search stats --es-url $EsUrl --index-name $demoSelected
if ($LASTEXITCODE -ne 0) { throw 'Impossibile leggere il corpus.' }
Write-Host "Indice selezionato: $demoSelected (nessuna ricostruzione). Demo: http://127.0.0.1:$Port"
if (-not $NoBrowser) {
    $demoWaitAndOpen = @'
import sys,time,urllib.request,webbrowser
url=sys.argv[1]
for _ in range(60):
    try:
        with urllib.request.urlopen(url+'/health',timeout=1) as r:
            if r.status==200:
                webbrowser.open(url)
                break
    except OSError:
        time.sleep(1)
'@
    # Il helper attende /health; il server resta nel terminale e si ferma con Ctrl+C.
    $demoHelper = Join-Path $demoRoot '.reproduction/demo/open_when_ready.py'
    New-Item -ItemType Directory -Force -Path (Split-Path $demoHelper -Parent) | Out-Null
    Set-Content -LiteralPath $demoHelper -Value $demoWaitAndOpen -Encoding UTF8
    Start-Process -FilePath $demoPython -ArgumentList '-B',("`"$demoHelper`""),"http://127.0.0.1:$Port" -WindowStyle Hidden
}
& $demoPython -B -m wikinews_search serve --es-url $EsUrl --index-name $demoSelected --port $Port
exit $LASTEXITCODE
