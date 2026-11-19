"""Post-experiment reporting and figures; never run alongside measured workload."""
import collections, csv, html, json, math, statistics as st, sys, zipfile
from pathlib import Path
import benchmark as b
R=b.ROOT
def csvread(name):
    with (R/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def blind():
    if not (R/'blind_candidates.jsonl').exists(): return
    candidates=[json.loads(x) for x in (R/'blind_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    data=json.dumps(candidates,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="it"><meta charset="utf-8"><title>Validazione cieca Wikinews</title><style>body{font:17px system-ui;max-width:1000px;margin:30px auto;padding:0 20px}header{position:sticky;top:0;background:white;padding:12px 0;border-bottom:1px solid #aaa}button,input,select{font:inherit;padding:8px}article{margin:24px 0;padding:18px;border:1px solid #aaa}pre{white-space:pre-wrap;font:16px/1.5 system-ui}label{display:inline-block;padding:8px}small{display:block}nav{margin-top:12px}</style><header><h1>Valutazione di rilevanza</h1><label>Valutatore <input id="assessor" placeholder="Identificativo personale"></label><button id="export">Esporta CSV</button><span id="progress"></span><nav><select id="queries"></select></nav></header><p>Giudicare rispetto all'intento, leggendo il testo. 0 = non pertinente; 1 = parzialmente pertinente; 2 = direttamente pertinente. Nessuna etichetta è preselezionata. Consultare ANNOTATION_GUIDE.md. I dati sono conservati solo in questo browser; esportare il CSV e conservarlo.</p><main id="main"></main><script>const data=DATA;let state={};const a=document.querySelector('#assessor'),q=document.querySelector('#queries'),main=document.querySelector('#main');const key=()=> 'wnbench20261118_'+a.value.trim();function load(){try{state=JSON.parse(localStorage.getItem(key())||'{}')}catch{state={}}render()}function persist(){if(a.value.trim())localStorage.setItem(key(),JSON.stringify(state));progress()}function progress(){document.querySelector('#progress').textContent=' '+Object.values(state).filter(x=>x.grade!=='').length+'/'+data.length+' giudizi'}const ids=[...new Set(data.map(x=>x.query_id))].sort();for(const id of ids){const x=data.find(x=>x.query_id===id),o=document.createElement('option');o.value=id;o.textContent=id+' — '+x.query;q.append(o)}function render(){main.replaceChildren();for(const x of data.filter(x=>x.query_id===q.value)){const article=document.createElement('article');const h=document.createElement('h2');h.textContent=x.title;article.append(h);const intent=document.createElement('p');intent.textContent='Intento: '+x.intent;article.append(intent);const meta=document.createElement('small');meta.textContent=x.query_id+' / '+x.candidate_id;article.append(meta);const text=document.createElement('pre');text.textContent=x.body;article.append(text);const id=x.query_id+'|'+x.candidate_id;for(const [grade,label]of [['0','Non pertinente'],['1','Parzialmente pertinente'],['2','Direttamente pertinente']]){const l=document.createElement('label'),i=document.createElement('input');i.type='radio';i.name=id;i.value=grade;i.checked=state[id]?.grade===grade;i.onchange=()=>{state[id]={grade,note:state[id]?.note||''};persist()};l.append(i,' '+grade+' '+label);article.append(l)}const note=document.createElement('input');note.placeholder='Nota facoltativa';note.value=state[id]?.note||'';note.onchange=()=>{state[id]={grade:state[id]?.grade??'',note:note.value};persist()};article.append(note);main.append(article)}progress()}a.onchange=load;q.onchange=render;document.querySelector('#export').onclick=()=>{if(!a.value.trim()){alert('Inserire il nome del valutatore');return}const esc=x=>'"'+String(x).replaceAll('"','""')+'"';const lines=[['query_id','candidate_id','grade','assessor','note'],...data.map(x=>{const s=state[x.query_id+'|'+x.candidate_id]||{};return[x.query_id,x.candidate_id,s.grade??'',a.value.trim(),s.note||'']})];const link=document.createElement('a');link.href=URL.createObjectURL(new Blob(['\\ufeff'+lines.map(l=>l.map(esc).join(',')).join('\\r\\n')],{type:'text/csv;charset=utf-8'}));link.download='annotation_'+a.value.trim()+'.csv';link.click();URL.revokeObjectURL(link.href)};render();</script></html>'''.replace('DATA',data)
    namespace='wnbench_'+b.sha(R/'blind_candidates.jsonl')[:20]+'_'
    page=page.replace("'wnbench20261118_'+a.value.trim()",json.dumps(namespace)+"+a.value.trim()")
    (R/'blind_annotation.html').write_text(page,encoding='utf-8')
    with zipfile.ZipFile(R/'blind_assessor_package.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['blind_annotation.html','blind_candidates.jsonl','validation_queries.json','annotation_assessor_1.csv','annotation_assessor_2.csv','ANNOTATION_GUIDE.md']: z.write(R/name,name)

def telemetry():
    grouped=collections.defaultdict(list)
    if not (R/'telemetry.jsonl').exists(): return
    with (R/'telemetry.jsonl').open(encoding='utf-8') as f:
        for line in f:
            x=json.loads(line); nodes=list(x['stats']['nodes'].values()); n=nodes[0]
            grouped[x['cell']].append(dict(time=x['unix_s'],es_cpu=n['process']['cpu']['percent'],heap=n['jvm']['mem']['heap_used_in_bytes'],heap_pct=n['jvm']['mem']['heap_used_percent'],host_available=x['host_memory']['available_physical_bytes'],host_mem_load=x['host_memory']['load_percent'],host_cpu=x['host_cpu_cumulative_100ns']))
    out=[]
    for cell,xx in grouped.items():
        cpu=[]
        for a,c in zip(xx,xx[1:]):
            old=a['host_cpu']; new=c['host_cpu']; total=new['kernel']+new['user']-old['kernel']-old['user']; idle=new['idle']-old['idle']
            if total>0: cpu.append(100*(1-idle/total))
        out.append(dict(cell=cell,samples=len(xx),es_process_cpu_pct_mean=st.mean(x['es_cpu'] for x in xx),es_process_cpu_pct_max=max(x['es_cpu'] for x in xx),heap_bytes_mean=st.mean(x['heap'] for x in xx),heap_bytes_max=max(x['heap'] for x in xx),host_available_bytes_min=min(x['host_available'] for x in xx),host_mem_load_max=max(x['host_mem_load'] for x in xx),host_cpu_pct_mean=st.mean(cpu) if cpu else '',host_cpu_pct_max=max(cpu) if cpu else ''))
    b.rows('telemetry_summary.csv',out)

def latency_components():
    results=[]; current=None; service=[]; queue=[]; cells={x['cell']:x for x in b.read('search_cells.json')}
    def emit(cell):
        x=cells[cell]
        results.append(dict(cell=cell,**{k:x[k] for k in ['path','scenario','config','clients','replicate']},service_p50_ms=b.percentile(service,.5),service_p95_ms=b.percentile(service,.95),dispatch_p50_ms=b.percentile(queue,.5),dispatch_p95_ms=b.percentile(queue,.95)))
    with (R/'search_raw.csv').open(encoding='utf-8',newline='') as f:
        for x in csv.DictReader(f):
            cell=int(x['cell'])
            if cell!=current:
                if current is not None: emit(current)
                current=cell;service=[];queue=[]
            if x['status']=='200' and not x['error']: service.append(float(x['service_ms']));queue.append(float(x['queue_ms']))
    if current is not None: emit(current)
    b.rows('search_latency_components.csv',results); groups=collections.defaultdict(list)
    for x in results: groups[tuple(x[k] for k in ['path','scenario','config','clients'])].append(x)
    out=[]
    for key,g in groups.items():
        for metric in ['service_p50_ms','service_p95_ms','dispatch_p50_ms','dispatch_p95_ms']:
            v=[x[metric] for x in g if x[metric] is not None];lo,hi=b.ci(v)
            out.append(dict(zip(['path','scenario','config','clients'],key),metric=metric,replicates=len(v),mean=st.mean(v),sd=st.stdev(v) if len(v)>1 else '',ci95_low=lo,ci95_high=hi))
    b.rows('search_latency_components_summary.csv',out)
    effects=[]
    for path in ['elasticsearch','flask_html']:
        for scenario in ['controlled','capacity']:
            for clients in [1,4,8,16]:
                for a,c in [('A','B'),('B','C')]:
                    left={x['replicate']:x for x in groups.get((path,scenario,a,clients),[])};right={x['replicate']:x for x in groups.get((path,scenario,c,clients),[])}
                    for metric in ['service_p50_ms','service_p95_ms','dispatch_p50_ms','dispatch_p95_ms']:
                        v=[right[r][metric]-left[r][metric] for r in left.keys()&right.keys() if right[r][metric] is not None and left[r][metric] is not None]
                        if v:
                            lo,hi=b.ci(v);effects.append(dict(path=path,scenario=scenario,clients=clients,contrast=c+'-'+a,metric=metric,paired_replicates=len(v),difference=st.mean(v),ci95_low=lo,ci95_high=hi))
    if effects:b.rows('search_latency_components_effects.csv',effects)

def figures():
    # Matplotlib is deliberately imported only after experiments have stopped.
    import os
    os.environ['MPLCONFIGDIR']=str(R/'plot_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.dpi':150,'font.size':10})
    colors={'A':'#4565ad','B':'#00806c','C':'#d97700'}; figs=R/'figures'; figs.mkdir(exist_ok=True)
    cells=b.read('search_cells.json') if (R/'search_cells.json').exists() else []
    for path in ['elasticsearch','flask_html']:
        fig,axs=plt.subplots(2,2,figsize=(11,7),layout='constrained')
        for i,scenario in enumerate(['controlled','capacity']):
            for j,metric in enumerate(['p95_ms','throughput']):
                ax=axs[i,j]
                for k in b.CONFIGS:
                    xx=[]; yy=[]; lows=[]; highs=[]
                    for c in [1,4,8,16]:
                        v=[x[metric] for x in cells if x['path']==path and x['scenario']==scenario and x['config']==k and x['clients']==c and x[metric] is not None]
                        if not v: continue
                        mean=st.mean(v); lo,hi=b.ci(v); xx.append(c); yy.append(mean); lows.append(mean-lo if lo is not None else 0); highs.append(hi-mean if hi is not None else 0)
                        ax.scatter([c]*len(v),v,color=colors[k],alpha=.3,s=12)
                    if xx: ax.errorbar(xx,yy,yerr=[lows,highs],label=k,color=colors[k],capsize=3,marker='o')
                ax.set_title(scenario); ax.set_xlabel('Client massimi'); ax.set_ylabel('p95 dal tempo programmato (ms)' if metric=='p95_ms' else 'Richieste riuscite / secondo'); ax.set_xticks([1,4,8,16]); ax.grid(alpha=.2); ax.legend()
        fig.suptitle(f'{path}: medie delle repliche e IC bootstrap 95% (n=5); punti = repliche')
        fig.savefig(figs/f'{path}.png'); fig.savefig(figs/f'{path}.svg'); plt.close(fig)
    idx=[x for x in csvread('indexing_raw.csv') if not x['error']]
    fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for ax,metric,label in zip(axs,['duration_s','docs_s','store_bytes'],['Durata (s)','Documenti unici / s','Store primario (MiB)']):
        for i,mode in enumerate(['pipeline','preprocessed']):
            for j,analyzer in enumerate(['standard','italiano']):
                v=[float(x[metric])/(1024**2 if metric=='store_bytes' else 1) for x in idx if x['mode']==mode and x['analyzer']==analyzer]; x=i+(j-.5)*.24
                if not v: continue
                mean=st.mean(v); lo,hi=b.ci(v); ax.errorbar([x],[mean],yerr=[[mean-lo],[hi-mean]],color=colors['A' if j==0 else 'B'],marker='o',capsize=4,label=analyzer if i==0 else None); ax.scatter([x]*len(v),v,alpha=.35,s=12,color=colors['A' if j==0 else 'B'])
        ax.set_xticks([0,1],['HTML + Bulk','Preprocessato + Bulk']); ax.set_ylabel(label); ax.grid(alpha=.2); ax.legend()
    fig.suptitle('Indicizzazione: cinque repliche per condizione, IC bootstrap 95%')
    fig.savefig(figs/'indexing.png'); fig.savefig(figs/'indexing.svg'); plt.close(fig)
    if (R/'search_effects.csv').exists():
        effects=csvread('search_effects.csv'); chosen=[x for x in effects if x['metric']=='p95_ms' and x['scenario']=='controlled']; fig,ax=plt.subplots(figsize=(9,7),layout='constrained')
        for i,x in enumerate(chosen):
            mean=float(x['difference']); lo=float(x['ci95_low']); hi=float(x['ci95_high']); ax.errorbar(mean,i,xerr=[[mean-lo],[hi-mean]],fmt='o',color=colors['B' if x['contrast']=='B-A' else 'C'],capsize=3)
        ax.set_yticks(range(len(chosen)),[f"{x['path']} c={x['clients']} {x['contrast']}" for x in chosen]); ax.axvline(0,color='gray',linestyle='--'); ax.set_xlabel('Differenza p95 client (ms), IC appaiato 95%'); ax.set_title('Stesso carico offerto: 8 richieste/s; IC non corretti per confronti multipli'); ax.grid(axis='x',alpha=.2)
        fig.savefig(figs/'controlled_effects.png'); fig.savefig(figs/'controlled_effects.svg'); plt.close(fig)
    if (R/'search_latency_components_summary.csv').exists():
        data=csvread('search_latency_components_summary.csv');fig,axs=plt.subplots(2,2,figsize=(11,7),layout='constrained')
        for i,path in enumerate(['elasticsearch','flask_html']):
            for j,metric in enumerate(['service_p95_ms','dispatch_p95_ms']):
                ax=axs[i,j]
                for k in b.CONFIGS:
                    g=sorted([x for x in data if x['path']==path and x['scenario']=='controlled' and x['config']==k and x['metric']==metric],key=lambda x:int(x['clients']))
                    if not g: continue
                    means=[float(x['mean']) for x in g];ax.errorbar([int(x['clients']) for x in g],means,yerr=[[max(0,float(x['mean'])-float(x['ci95_low'])) for x in g],[max(0,float(x['ci95_high'])-float(x['mean'])) for x in g]],marker='o',color=colors[k],label=k,capsize=3)
                ax.set_title(path);ax.set_xlabel('Client massimi, carico offerto 8/s');ax.set_ylabel('p95 richiesta effettiva (ms)' if j==0 else 'p95 ritardo dispatch (ms)');ax.set_xticks([1,4,8,16]);ax.grid(alpha=.2);ax.legend()
        fig.suptitle('Componenti temporali: IC fra repliche; i percentili delle componenti non si sommano')
        fig.savefig(figs/'latency_components.png');fig.savefig(figs/'latency_components.svg');plt.close(fig)

def verify():
    m=b.read('manifest.json'); differences=[]
    for rel,expected in {**m['source_sha256'],**m['preserved_sha256']}.items():
        if b.sha(b.REPO/rel)!=expected: differences.append(rel)
    inputs={'dump_unchanged':b.sha(m['dump'])==m['dump_sha256'],'preprocessed_unchanged':b.sha(R/'preprocessed.jsonl')==m['preprocessed_sha256'],'workload_unchanged':b.sha(R/'workload.json')==m['workload_sha256'],'harness_unchanged':b.sha(R/'benchmark.py')==m['harness_sha256']}
    b.save('preservation_check.json',dict(changed_files=differences,source_files_checked=len(m['source_sha256']),original_artifacts_checked=len(m['preserved_sha256']),no_git_commands_used=True,input_checks=inputs))
    assert not differences
    assert all(inputs.values())
    artifacts={str(p.relative_to(R)):b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['artifact_checksums.json','results.zip'] and 'vendor' not in p.parts and '__pycache__' not in p.parts}
    b.save('artifact_checksums.json',artifacts)
    with zipfile.ZipFile(R/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in [*artifacts,'artifact_checksums.json']: z.write(R/name,name)
def collect():
    try:
        es=b.client(); b.save('benchmark_index_metadata.json',dict(es.indices.get(index='wnbench_*',expand_wildcards='all')))
        b.save('open_index_postrun_stats.json',dict(es.indices.stats(metric='docs,segments,store,search,indexing')))
        before=b.read('cluster_before.json')['indices']; checks={}
        for name,meta in before.items():
            now=es.indices.get(index=name)[name]
            checks[name]=dict(uuid_before=meta['settings']['index']['uuid'],uuid_after=now['settings']['index']['uuid'],uuid_unchanged=meta['settings']['index']['uuid']==now['settings']['index']['uuid'],final_documents=es.count(index=name)['count'])
        b.save('preexisting_indices_check.json',checks)
        names=b.read('manifest.json')['benchmark_indices']; counts=[]
        for q in b.read('workload.json')['queries']:
            for k in b.CONFIGS:
                response=es.search(index=names[b.CONFIGS[k][0]],**b.body(q['query'],k),request_cache=False)
                counts.append(dict(query_id=q['id'],query=q['query'],category=q['category'],config=k,total_hits=response['hits']['total']['value'],returned_hits=len(response['hits']['hits']),timed_out=response.get('timed_out'),failed_shards=response['_shards']['failed']))
        b.rows('postrun_workload_match_counts.csv',counts)
        opened=set(es.indices.get(index='wnbench_*',expand_wildcards='open'))
        expected=next(iter(b.read('corpus_equality.json').values()))['source_sha256'];verification=[]
        import hashlib
        for item in b.read('created_indices.json'):
            name=item['index'];was_open=name in opened
            if not was_open:es.indices.open(index=name,wait_for_active_shards='all')
            try:
                docs=sorted((hit['_id'],json.dumps(hit['_source'],ensure_ascii=False,sort_keys=True)) for hit in b.helpers.scan(es,index=name,query={'query':{'match_all':{}}}))
                digest=hashlib.sha256(json.dumps(docs,ensure_ascii=False).encode()).hexdigest()
                verification.append(dict(index=name,mode=item['mode'],analyzer=item['analyzer'],replicate=item['replicate'],documents=len(docs),source_sha256=digest,matches_search_corpus=digest==expected,initially_open=was_open))
            finally:
                if not was_open:es.indices.close(index=name)
        b.save('all_index_corpus_verification.json',verification)
        final_opened=set(es.indices.get(index='wnbench_*',expand_wildcards='open'))
        b.save('index_state_restoration.json',dict(initial_open_names=sorted(opened),final_open_names=sorted(final_opened),restored=opened==final_opened))
        es.close()
    except Exception as ex: b.save('postflight_collection_error.json',dict(error=repr(ex)))
if __name__=='__main__':
    if '--blind' in sys.argv: blind()
    elif '--verify' in sys.argv: verify()
    else: collect(); b.aggregate(); telemetry(); latency_components(); blind(); figures()
