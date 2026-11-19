"""External, append-only experimental harness. Never deletes an Elasticsearch index."""
import argparse, collections, concurrent.futures as cf, copy, csv, ctypes, hashlib
import importlib.metadata as md, json, math, os, platform, random, statistics as st
import sys, threading, time, traceback, uuid, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path(r'C:\Users\proti\Desktop\dev\wikinews-search-elasticsearch')
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
from wikinews_search.indexer import SETTINGS, MAPPINGS, iter_articles, article_to_source, make_client
from wikinews_search.searcher import build_body
from wikinews_search.statistics import IndexStats
from elasticsearch import helpers

SEED = 20261118
CONFIGS = {'A': ('standard', ['title','body']), 'B': ('italiano',['title','body']), 'C': ('italiano',['title^3','body'])}
def save(p, obj):
    (ROOT/p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def rows(p, data, fields=None):
    data=list(data)
    with (ROOT/p).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(data[0])); w.writeheader(); w.writerows(data)
def log(s): print(time.strftime('%H:%M:%S'),s,flush=True)
def percentile(v,p): return sorted(v)[max(0,math.ceil(len(v)*p)-1)] if v else None
def ci(v,seed=SEED):
    if len(v)<2: return [None,None]
    r=random.Random(seed); b=sorted(st.mean(r.choices(v,k=len(v))) for _ in range(10000))
    return [percentile(b,.025),percentile(b,.975)]

def prepare():
    if (ROOT/'manifest.json').exists(): raise RuntimeError('Output already initialized')
    # Written before any cluster search or ranking inspection. Deliberate category quotas.
    categories={
      'nomi_propri':['Giorgio Napolitano','Romano Prodi','Angela Merkel','Vladimir Putin','Donald Trump','Matteo Renzi','Giuseppe Conte','Mario Draghi','Giorgia Meloni','Luigi Di Maio','Benedetto XVI','Nelson Mandela','Fidel Castro','Michael Schumacher'],
      'eventi':['terremoto Haiti','terremoto Nepal','tsunami Giappone','attentati Parigi','attentati Londra','Brexit referendum','Mondiali Sudafrica','Olimpiadi Londra','Giro Italia','Festival Sanremo','eruzione Etna','incendio Notre Dame','Expo Milano','crisi Grecia'],
      'generiche':['disoccupazione','cambiamento climatico','immigrazione','sanita pubblica','istruzione scuola','ricerca scientifica','sicurezza stradale','diritti civili','trasporto pubblico','mercati finanziari','inquinamento atmosferico','criminalita organizzata','telecomunicazioni','giustizia penale'],
      'flessioni':['lavoratore','lavoratori','studente','studenti','manifestante','manifestanti','ospedale','ospedali','incendio','incendi','sindaco','sindaci','migrante','migranti'],
      'accenti':['università','universita','perché','perche','società','societa','libertà','liberta','qualità','qualita','povertà','poverta','comunità','comunita'],
      'frasi':['"unione europea"','"consiglio dei ministri"','"corte costituzionale"','"diritti umani"','"stazione spaziale"','"protezione civile"','"cambiamento climatico"','"coppa del mondo"','"libertà di stampa"','"forze armate"','"stato di emergenza"','"salute pubblica"','"pena di morte"','"acqua potabile"'],
      'ambigue':['calcio','camera','lega','stelle','ponte','opera','capitale','borsa','marcia','corrente']}
    old=json.loads((REPO/'experiments/queries.json').read_text(encoding='utf-8'))
    queries=[]
    for cat,qq in categories.items():
        for i,q in enumerate(qq):
            group=f'{cat}_{i//2}' if cat in ('flessioni','accenti') else f'{cat}_{i}'
            queries.append(dict(id=f'w{len(queries)+1:03}',query=q,category=cat,group=group))
    assert len(queries)==94 and not ({q['query'].casefold() for q in queries}&{q['query'].casefold() for q in old})
    random.Random(SEED).shuffle(queries)
    intents=[
      ('Giorgio Napolitano','Attività istituzionale e vicende politiche di Giorgio Napolitano.'),
      ('Angela Merkel','Attività politica e decisioni di governo di Angela Merkel.'),
      ('terremoto Haiti','Terremoto ad Haiti del 2010, soccorsi e conseguenze.'),
      ('attentati Parigi','Attentati a Parigi del 2015, indagini e conseguenze.'),
      ('Brexit referendum','Referendum britannico del 2016 sulla permanenza nella UE.'),
      ('disoccupazione','Dati e politiche riguardanti la mancanza di lavoro.'),
      ('cambiamento climatico','Cause, conseguenze e politiche sul cambiamento climatico.'),
      ('lavoratore','Condizioni, diritti e sicurezza delle persone che lavorano.'),
      ('lavoratori','Condizioni, diritti e sicurezza delle persone che lavorano.'),
      ('studente','Condizioni, diritti e iniziative delle persone che studiano.'),
      ('studenti','Condizioni, diritti e iniziative delle persone che studiano.'),
      ('università','Istituzioni universitarie, ricerca, didattica e politiche accademiche.'),
      ('universita','Istituzioni universitarie, ricerca, didattica e politiche accademiche.'),
      ('"diritti umani"','Violazioni, tutela e politiche relative ai diritti umani.'),
      ('"stazione spaziale"','Missioni, equipaggi e attività delle stazioni spaziali.'),
      ('calcio','Sport del calcio: competizioni, squadre e risultati.'),
      ('camera','Camera dei deputati italiana: lavori e decisioni parlamentari.'),
      ('borsa','Mercati finanziari azionari e loro andamento.')]
    validation=[]
    for q,intent in intents:
        x=next(copy.copy(x) for x in queries if x['query']==q); x['id']='v'+str(len(validation)+1).zfill(2); x['intent']=intent; validation.append(x)
    save('workload.json',dict(seed=SEED,synthetic=True,selection='Selezione deliberata a quote, senza log utenti e senza consultare ranking. Nessuna rappresentatività empirica degli utenti. 14 query per sei categorie, 10 ambigue. Escluse corrispondenze esatte alle 27 diagnostiche; sovrapposizioni tematiche possibili.',queries=queries,validation=validation,validation_disjoint_from_diagnostics=True,validation_overlaps_performance_by_design=True))
    rawfields=['path','scenario','replicate','cell','config','clients','query_id','sequence','scheduled_s','start_s','end_s','client_ms','service_ms','queue_ms','es_took_ms','status','error','response_bytes']
    rows('search_raw.csv',[],rawfields)
    rows('indexing_raw.csv',[],['mode','replicate','analyzer','index','duration_s','operations','documents','docs_s','bulk_errors','store_bytes','flush_s','error'])
    rows('search_summary.csv',[],['path','scenario','config','clients','replicates','metric','mean','sd','ci95_low','ci95_high'])
    rows('indexing_summary.csv',[],['mode','analyzer','replicates','metric','mean','sd','ci95_low','ci95_high'])
    rows('annotation_assessor_1.csv',[],['query_id','candidate_id','grade','assessor','note'])
    rows('annotation_assessor_2.csv',[],['query_id','candidate_id','grade','assessor','note'])
    dump=next((REPO/'data').glob('itwikinews*.tar.gz'))
    sources={str(p.relative_to(REPO)):sha(p) for p in (REPO/'wikinews_search').rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    originals={}
    for d in [REPO/'experiments/results-2026-11-17',REPO/'data/experiment-real']:
        target=ROOT/'preserved'/d.name; target.mkdir(parents=True)
        for p in d.iterdir():
            if p.is_file():
                import shutil
                shutil.copy2(p,target/p.name); originals[str(p.relative_to(REPO))]=sha(p)
    manifest=dict(seed=SEED,created_local=time.strftime('%Y-%m-%dT%H:%M:%S'),timezone='Europe/Rome',repo=str(REPO),output=str(ROOT),python=sys.version,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),packages={p:md.version(p) for p in ['elasticsearch','Flask','beautifulsoup4','lxml']},dump=str(dump),dump_sha256=sha(dump),source_sha256=sources,preserved_sha256=originals,workload_sha256=sha(ROOT/'workload.json'),configs=CONFIGS,protocol=dict(replicates=5,clients=[1,4,8,16],controlled_rps=8,controlled_requests=96,capacity_seconds=30,warmup_requests=32,warmup_excluded=True,bootstrap_resamples=10000,capacity_slo_p95_ms=500,capacity_max_error_rate=.01,capacity_window_throughput_cv=.15,capacity_windows=3,capacity_interpretation='Observed 30-second sustainable throughput envelope at tested concurrency; not proof of long-run maximum.',bulk_chunk_size=500,independence='Separate sequential runs and new indexing destinations; same host, warm filesystem, not independent hardware samples.',cache='Natural warm cache. No cache clearing. Equal request_cache=false for direct ES and adapter Flask.',payload='build_body page=1 size=10, normal Web source/highlight/facets; no full-body candidate source.',primary_ranking_metric='nDCG@10',secondary_ranking_metrics=['P@5','MRR@10']),status={})
    save('manifest.json',manifest)
    save('validation_queries.json',validation)
    # Randomized complete blocks: each cell appears once in every independent replicate.
    r=random.Random(SEED); schedule=[]
    for rep in range(1,6):
        cells=[dict(path=p,scenario=s,clients=c,config=k,replicate=rep) for p in ['elasticsearch','flask_html'] for s in ['controlled','capacity'] for c in [1,4,8,16] for k in CONFIGS]
        r.shuffle(cells); schedule+=cells
    save('search_schedule.json',schedule)
    order=[]
    for mode in ['pipeline','preprocessed']:
        for rep in range(1,6):
            for analyzer in (['standard','italiano'] if rep%2 else ['italiano','standard']): order.append(dict(mode=mode,replicate=rep,analyzer=analyzer))
    save('indexing_schedule.json',order)
    log('Frozen workload and protocol: 94 performance, 18 validation queries')

def preprocess():
    m=read('manifest.json'); stats=IndexStats(); started=time.perf_counter(); n=0
    with (ROOT/'preprocessed.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for a in iter_articles(m['dump'],stats):
            f.write(json.dumps(article_to_source(a),ensure_ascii=False,separators=(',',':'))+'\n'); n+=1
            if n%2000==0: log(f'Preprocessing {n} valid operations')
    save('preprocessing.json',dict(duration_s=time.perf_counter()-started,operations=n,stats=stats.to_dict(),sha256=sha(ROOT/'preprocessed.jsonl')))
    log('Preprocessing complete')

def client():
    from elasticsearch import Elasticsearch
    from wikinews_search.config import DEFAULT_ES_URL
    auth={'basic_auth':(os.environ['ES_USERNAME'],os.environ.get('ES_PASSWORD',''))} if os.environ.get('ES_USERNAME') else {}
    endpoint=DEFAULT_ES_URL.replace('://localhost:', '://127.0.0.1:')
    return Elasticsearch(endpoint,connections_per_node=32,max_retries=0,request_timeout=30,**auth)
def snapshot(es,label):
    data={}
    for key,fn in [('info',lambda:dict(es.info())),('health',lambda:dict(es.cluster.health())),('nodes',lambda:dict(es.nodes.info())),('stats',lambda:dict(es.nodes.stats(metric='os,process,jvm,indices,fs'))),('indices',lambda:dict(es.indices.get(index='*'))),('tasks',lambda:dict(es.tasks.list(detailed=True)))]:
        try: data[key]=fn()
        except Exception as ex: data[key]={'error':repr(ex)}
    save(f'cluster_{label}.json',data); return data

def append(p,d):
    with (ROOT/p).open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(d)); w.writerow(d)

def index_runs(es):
    m=read('manifest.json'); names={}; indexlog=[]
    for i,cell in enumerate(read('indexing_schedule.json')):
        name=f'wnbench_{SEED}_{uuid.uuid4().hex[:12]}_{cell["analyzer"]}'
        # Explicit collision guard, then CREATE only. No application create_index/build_index.
        assert not es.indices.exists(index=name)
        mapping=copy.deepcopy(MAPPINGS)
        for f in ['title','body']: mapping['properties'][f]['analyzer']=cell['analyzer']
        settings=copy.deepcopy(SETTINGS); settings['refresh_interval']='-1'
        stats=IndexStats(); count=0; errors=0; failure=''; started=time.perf_counter()
        try:
            es.indices.create(index=name,settings=settings,mappings=mapping)
            def sources():
                if cell['mode']=='pipeline':
                    for a in iter_articles(m['dump'],stats): yield article_to_source(a)
                else:
                    with (ROOT/'preprocessed.jsonl').open(encoding='utf-8') as f:
                        for line in f: yield json.loads(line)
            actions=({'_op_type':'index','_index':name,'_id':s['article_id'],'_source':s} for s in sources())
            for ok,item in helpers.streaming_bulk(es,actions,chunk_size=500,raise_on_error=False,raise_on_exception=True,max_retries=0):
                count+=int(ok); errors+=int(not ok)
                if not ok: append('bulk_errors.jsonl.csv',dict(index=name,error=json.dumps(item)))
            es.indices.refresh(index=name)
            elapsed=time.perf_counter()-started
            docs=es.count(index=name)['count']; fstart=time.perf_counter(); es.indices.flush(index=name); flush=time.perf_counter()-fstart
            size=es.indices.stats(index=name,metric='store')['_all']['primaries']['store']['size_in_bytes']
            es.indices.put_settings(index=name,settings={'refresh_interval':'1s'})
            if errors or count!=read('preprocessing.json')['operations']: raise RuntimeError('Bulk errors or corpus operation mismatch')
            names.setdefault(cell['analyzer'],name)
        except Exception as ex:
            failure=repr(ex); elapsed=time.perf_counter()-started; docs=size=flush=''
        row=dict(**cell,index=name,duration_s=elapsed,operations=count,documents=docs,docs_s=float(docs)/elapsed if docs!='' else '',bulk_errors=errors,store_bytes=size,flush_s=flush,error=failure)
        # Match predeclared CSV column order.
        row={k:row[k] for k in ['mode','replicate','analyzer','index','duration_s','operations','documents','docs_s','bulk_errors','store_bytes','flush_s','error']}
        append('indexing_raw.csv',row); indexlog.append(row); save('created_indices.json',indexlog)
        log(f'Indexing {i+1}/20 {cell}: {elapsed:.2f}s {count} operations errors={errors} {failure}')
        if failure: raise RuntimeError(failure)
        # Wait for background merges to finish; does not force-merge or destroy any index.
        settle(es)
        es.indices.close(index=name)
    for name in names.values(): es.indices.open(index=name,wait_for_active_shards='all')
    m=read('manifest.json'); m['benchmark_indices']=names; save('manifest.json',m)
    return names

def settle(es):
    deadline=time.monotonic()+120
    while True:
        s=es.indices.stats(metric='merge,indexing')['_all']['total']
        if s['merges']['current']==0 and s['indexing']['index_current']==0: return
        if time.monotonic()>deadline: raise RuntimeError('Background merges/indexing did not settle')
        time.sleep(1)

def body(q,k):
    b=build_body(q,1,10)
    for clause in b['query']['bool']['must']+b['query']['bool'].get('must_not',[]):
        if 'simple_query_string' in clause: clause['simple_query_string']['fields']=CONFIGS[k][1]
    return b

def corpus_check(es,names):
    hashes={}
    for analyzer,name in names.items():
        docs=sorted((h['_id'],json.dumps(h['_source'],ensure_ascii=False,sort_keys=True)) for h in helpers.scan(es,index=name,query={'query':{'match_all':{}}}))
        hashes[analyzer]={'count':len(docs),'source_sha256':hashlib.sha256(json.dumps(docs,ensure_ascii=False).encode()).hexdigest()}
    save('corpus_equality.json',hashes)
    assert len({x['source_sha256'] for x in hashes.values()})==1

def pool(es,names):
    queries=read('validation_queries.json'); rankings={}; mapping={}; candidates=[]
    r=random.Random(SEED+1)
    for q in queries:
        rankings[q['id']]={}; pooled={}
        for k in CONFIGS:
            b=body(q['query'],k); b['source']=['title','url','body']
            hits=es.search(index=names[CONFIGS[k][0]],**b)['hits']['hits']
            rankings[q['id']][k]=[h['_id'] for h in hits]
            for h in hits: pooled[h['_id']]=h['_source']
        ids=list(pooled); r.shuffle(ids)
        for docid in ids:
            cid=uuid.UUID(int=r.getrandbits(128)).hex[:16]
            mapping[q['id']+'|'+cid]=docid
            candidates.append(dict(query_id=q['id'],query=q['query'],intent=q['intent'],candidate_id=cid,**pooled[docid]))
    r.shuffle(candidates)
    save('ranking_private.json',dict(queries=queries,rankings=rankings,candidate_mapping=mapping))
    with (ROOT/'blind_candidates.jsonl').open('w',encoding='utf-8') as f:
        for x in candidates: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    template=[dict(query_id=x['query_id'],candidate_id=x['candidate_id'],grade='',assessor='',note='') for x in candidates]
    for a in [1,2]: rows(f'annotation_assessor_{a}.csv',template,['query_id','candidate_id','grade','assessor','note'])
    save('pool_counts.json',{q['id']:sum(c['query_id']==q['id'] for c in candidates) for q in queries})
    log(f'Blind pool complete: {len(candidates)} query/document pairs')

class Proxy:
    def __init__(self,es,k): self.es=es; self.k=k; self.local=threading.local()
    def __getattr__(self,name): return getattr(self.es,name)
    def search(self,**kw):
        for clause in kw.get('query',{}).get('bool',{}).get('must',[])+kw.get('query',{}).get('bool',{}).get('must_not',[]):
            if 'simple_query_string' in clause: clause['simple_query_string']['fields']=CONFIGS[self.k][1]
        response=self.es.search(**kw,request_cache=False); self.local.took=response.get('took'); return response

def flask_servers(es,names):
    from wikinews_search.webapp import create_app
    from werkzeug.serving import make_server, WSGIRequestHandler
    class Quiet(WSGIRequestHandler):
        def log(self,*a,**kw): pass
    servers={}
    for k in CONFIGS:
        proxy=Proxy(es,k); app=create_app(client=proxy,index_name=names[CONFIGS[k][0]])
        def add_header(resp,proxy=proxy):
            resp.headers['X-Benchmark-ES-Took']=str(getattr(proxy.local,'took','')); return resp
        app.after_request(add_header)
        server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet)
        threading.Thread(target=server.serve_forever,daemon=True).start(); servers[k]=server
    return servers

def telemetry(es,stop,cell):
    while not stop.is_set():
        try:
            s=dict(es.nodes.stats(metric='os,process,jvm,indices'))
            memory=ctypes.create_string_buffer(64); ctypes.c_ulong.from_buffer(memory).value=64
            ctypes.windll.kernel32.GlobalMemoryStatusEx(memory)
            host_memory={'load_percent':ctypes.c_ulong.from_buffer(memory,4).value,'total_physical_bytes':ctypes.c_ulonglong.from_buffer(memory,8).value,'available_physical_bytes':ctypes.c_ulonglong.from_buffer(memory,16).value}
            idle=ctypes.c_ulonglong(); kernel=ctypes.c_ulonglong(); user=ctypes.c_ulonglong()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user))
            with (ROOT/'telemetry.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(dict(cell=cell,unix_s=time.time(),host_memory=host_memory,host_cpu_cumulative_100ns={'idle':idle.value,'kernel':kernel.value,'user':user.value},stats=s))+'\n')
        except Exception as ex:
            with (ROOT/'telemetry_errors.txt').open('a') as f: f.write(repr(ex)+'\n')
        stop.wait(1)

def search_runs(es,names):
    servers=flask_servers(es,names); workload=read('workload.json')['queries']; summaries=[]
    try:
        for cellid,c in enumerate(read('search_schedule.json'),1):
            settle(es); k=c['config']; path=c['path']; n=c['clients']; rep=c['replicate']
            qq=list(workload); random.Random(SEED+rep).shuffle(qq)
            def request(q):
                if path=='elasticsearch':
                    resp=es.search(index=names[CONFIGS[k][0]],**body(q['query'],k),request_cache=False)
                    if resp.get('timed_out') or resp.get('_shards',{}).get('failed'): raise RuntimeError('ES timeout/shard failure')
                    return resp['took'],200,''
                url=f'http://127.0.0.1:{servers[k].server_port}/?'+urllib.parse.urlencode({'q':q['query']})
                with urllib.request.urlopen(url,timeout=30) as resp:
                    payload=resp.read()
                    return float(resp.headers['X-Benchmark-ES-Took']),resp.status,len(payload)
            for q in qq[:32]: request(q)
            stop=threading.Event(); monitor=threading.Thread(target=telemetry,args=(es,stop,cellid),daemon=True); monitor.start()
            start=time.perf_counter(); out=[]; lock=threading.Lock(); seq=[0]
            def one(i,scheduled):
                begin=time.perf_counter(); error=''; status=0; took=''; size=''
                try: took,status,size=request(qq[i%len(qq)])
                except Exception as ex: error=repr(ex)
                end=time.perf_counter()
                return dict(path=path,scenario=c['scenario'],replicate=rep,cell=cellid,config=k,clients=n,query_id=qq[i%len(qq)]['id'],sequence=i,scheduled_s=scheduled-start,start_s=begin-start,end_s=end-start,client_ms=(end-scheduled)*1000,service_ms=(end-begin)*1000,queue_ms=max(0,begin-scheduled)*1000,es_took_ms=took,status=status,error=error,response_bytes=size)
            with cf.ThreadPoolExecutor(max_workers=n) as executor:
                if c['scenario']=='controlled':
                    futures=[]
                    for i in range(96):
                        due=start+i/8; delay=due-time.perf_counter()
                        if delay>0: time.sleep(delay)
                        futures.append(executor.submit(one,i,due))
                    out=[f.result() for f in futures]
                else:
                    def worker():
                        data=[]
                        while time.perf_counter()<start+30:
                            with lock: i=seq[0]; seq[0]+=1
                            data.append(one(i,time.perf_counter()))
                        return data
                    futures=[executor.submit(worker) for _ in range(n)]
                    for f in futures: out+=f.result()
            elapsed=time.perf_counter()-start; stop.set(); monitor.join()
            with (ROOT/'search_raw.csv').open('a',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(out[0])); w.writerows(out)
            good=[x for x in out if not x['error'] and x['status']==200]; lat=[x['client_ms'] for x in good]
            windows=[sum(10*i<=x['end_s']<10*(i+1) for x in good)/10 for i in range(3)] if c['scenario']=='capacity' else []
            cv=st.pstdev(windows)/st.mean(windows) if windows and st.mean(windows)>0 else None
            result=dict(**c,cell=cellid,elapsed_s=elapsed,requests=len(out),errors=len(out)-len(good),throughput=len(good)/elapsed,p50_ms=percentile(lat,.5),p95_ms=percentile(lat,.95),es_p50_ms=percentile([float(x['es_took_ms']) for x in good],.5),es_p95_ms=percentile([float(x['es_took_ms']) for x in good],.95),window_rps=windows,window_cv=cv,sustainable_observed=(bool(good) and percentile(lat,.95)<=500 and (len(out)-len(good))/len(out)<=.01 and cv is not None and cv<=.15))
            summaries.append(result); save('search_cells.json',summaries)
            log(f'Search {cellid}/240 {path} {c["scenario"]} {k} c={n} rep={rep}: p95={result["p95_ms"]} throughput={result["throughput"]:.2f} errors={result["errors"]}')
    finally:
        for server in servers.values(): server.shutdown(); server.server_close()

def aggregate():
    output=[]; effects=[]
    if (ROOT/'search_cells.json').exists():
        cells=read('search_cells.json'); groups=collections.defaultdict(list)
        for x in cells: groups[tuple(x[k] for k in ['path','scenario','config','clients'])].append(x)
        for key,g in groups.items():
            for metric in ['p50_ms','p95_ms','throughput','errors','es_p50_ms','es_p95_ms']:
                v=[x[metric] for x in g if x[metric] is not None]; low,high=ci(v)
                output.append(dict(zip(['path','scenario','config','clients'],key),replicates=len(v),metric=metric,mean=st.mean(v),sd=st.stdev(v) if len(v)>1 else '',ci95_low=low,ci95_high=high))
        rows('search_summary.csv',output)
        for path in ['elasticsearch','flask_html']:
            for scenario in ['controlled','capacity']:
                for clients in [1,4,8,16]:
                    for a,b in [('A','B'),('B','C')]:
                        for metric in ['p50_ms','p95_ms','throughput']:
                            left={x['replicate']:x for x in groups.get((path,scenario,a,clients),[])}; right={x['replicate']:x for x in groups.get((path,scenario,b,clients),[])}
                            v=[right[r][metric]-left[r][metric] for r in left.keys()&right.keys() if right[r][metric] is not None and left[r][metric] is not None]
                            if v:
                                lo,hi=ci(v); effects.append(dict(path=path,scenario=scenario,clients=clients,contrast=b+'-'+a,metric=metric,paired_replicates=len(v),difference=st.mean(v),ci95_low=lo,ci95_high=hi))
        if effects: rows('search_effects.csv',effects)
    groups=collections.defaultdict(list)
    with (ROOT/'indexing_raw.csv').open(encoding='utf-8') as f:
        for x in csv.DictReader(f):
            if not x['error']: groups[(x['mode'],x['analyzer'])].append(x)
    out=[]
    for key,g in groups.items():
        for metric in ['duration_s','docs_s','store_bytes','bulk_errors']:
            v=[float(x[metric]) for x in g]; lo,hi=ci(v)
            out.append(dict(mode=key[0],analyzer=key[1],replicates=len(v),metric=metric,mean=st.mean(v),sd=st.stdev(v) if len(v)>1 else '',ci95_low=lo,ci95_high=hi))
    if out: rows('indexing_summary.csv',out)
    effect=[]
    for mode in ['pipeline','preprocessed']:
        a={x['replicate']:x for x in groups.get((mode,'standard'),[])}; b={x['replicate']:x for x in groups.get((mode,'italiano'),[])}
        for metric in ['duration_s','docs_s','store_bytes']:
            v=[float(b[r][metric])-float(a[r][metric]) for r in a.keys()&b.keys()]
            if v:
                lo,hi=ci(v); effect.append(dict(mode=mode,contrast='italiano-standard',metric=metric,paired_replicates=len(v),difference=st.mean(v),ci95_low=lo,ci95_high=hi))
    if effect: rows('indexing_effects.csv',effect)

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['prepare','preprocess','online','aggregate']); args=p.parse_args()
    if args.command=='prepare': prepare()
    elif args.command=='preprocess': preprocess()
    elif args.command=='aggregate': aggregate()
    else:
        es=client(); m=read('manifest.json')
        try:
            es.info(); snapshot(es,'before'); m['status']['elasticsearch']='reachable'; save('manifest.json',m)
            names=index_runs(es); corpus_check(es,names); pool(es,names); search_runs(es,names)
            snapshot(es,'after'); m=read('manifest.json'); m['status']['online']='completed'; save('manifest.json',m)
        except Exception as ex:
            m=read('manifest.json'); m['status']['online']='incomplete'; m['online_error']=traceback.format_exc(); save('manifest.json',m); raise
        finally: aggregate()
if __name__=='__main__': main()
