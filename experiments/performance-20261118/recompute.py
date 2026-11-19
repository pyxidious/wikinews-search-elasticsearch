"""Recompute original performance statistics from raw files, offline. No ES imports."""
import argparse,collections,csv,hashlib,io,json,math,random,statistics as st,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SEED=20261118
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,data):
 with Path(p).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def percentile(v,p):return sorted(v)[max(0,math.ceil(p*len(v))-1)] if v else None
def ci(v):
 rng=random.Random(SEED);res=sorted(st.mean(rng.choices(v,k=len(v))) for _ in range(10000));return percentile(res,.025),percentile(res,.975)
def summary(cells,metrics):
 grouped=collections.defaultdict(list)
 for x in cells:grouped[tuple(x[k] for k in ['path','scenario','config','clients'])].append(x)
 output=[]
 for key,items in grouped.items():
  items=sorted(items,key=lambda x:x['replicate'])
  if len(items)!=5 or {x['replicate'] for x in items}!=set(range(1,6)):raise ValueError('Not five complete experimental replicates')
  for metric in metrics:
   v=[x[metric] for x in items];lo,hi=ci(v);output.append(dict(zip(['path','scenario','config','clients'],key),replicates=5,metric=metric,mean=st.mean(v),sd=st.stdev(v),ci95_low=lo,ci95_high=hi))
 return output
def compare(actual,reference,keys,numeric):
 now={tuple(str(x[k]) for k in keys):x for x in actual};bad=[]
 if len(now)!=len(reference):bad.append({'reason':'row count'})
 for row in reference:
  key=tuple(str(row[k]) for k in keys)
  if key not in now:bad.append({'key':key});continue
  for field in numeric:
   if not math.isclose(float(row[field]),float(now[key][field]),rel_tol=1e-12,abs_tol=1e-9):bad.append({'key':key,'field':field,'reference':row[field],'actual':now[key][field]})
 return bad
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw-archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
 if out.is_relative_to(ROOT.resolve()):raise ValueError('Use an output outside the frozen publication directory')
 spec=read(ROOT/'RAW_DATA.json')
 manifest=read(ROOT/'manifest.json')
 for name,expected in manifest['files'].items():
  file=(ROOT/name).resolve()
  if not file.is_relative_to(ROOT.resolve()) or not file.is_file() or digest(file)!=expected:raise ValueError('Publication manifest mismatch: '+name)
 if digest(a.raw_archive)!=spec['archive_sha256']:raise ValueError('Wrong raw archive')
 original=ROOT/'original';frozen=read(original/'search_cells.json');meta={x['cell']:x for x in frozen};computed=[];current=None;good=[];count=0;errors=0
 def emit(cell):
  x=meta[cell];win=[sum(10*i<=r['end_s']<10*(i+1) for r in good)/10 for i in range(3)] if x['scenario']=='capacity' else []
  cv=st.pstdev(win)/st.mean(win) if win else None
  return dict(**{k:x[k] for k in ['cell','path','scenario','config','clients','replicate']},requests=count,errors=errors,throughput=len(good)/x['elapsed_s'],p50_ms=percentile([r['client_ms'] for r in good],.5),p95_ms=percentile([r['client_ms'] for r in good],.95),es_p50_ms=percentile([r['es_took_ms'] for r in good],.5),es_p95_ms=percentile([r['es_took_ms'] for r in good],.95),service_p50_ms=percentile([r['service_ms'] for r in good],.5),service_p95_ms=percentile([r['service_ms'] for r in good],.95),dispatch_p50_ms=percentile([r['queue_ms'] for r in good],.5),dispatch_p95_ms=percentile([r['queue_ms'] for r in good],.95),window_cv=cv,sustainable_observed=bool(good) and percentile([r['client_ms'] for r in good],.95)<=500 and errors/count<=.01 and cv is not None and cv<=.15)
 with zipfile.ZipFile(a.raw_archive) as z:
  for name,info in spec['raw_files'].items():
   h=hashlib.sha256()
   with z.open(name) as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
   if h.hexdigest()!=info['sha256']:raise ValueError('Raw member checksum mismatch: '+name)
  with z.open('search_raw.csv') as f:
   for row in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8',newline='')):
    cell=int(row['cell']);m=meta[cell]
    if any(str(row[k])!=str(m[k]) for k in ['path','scenario','clients','config','replicate']):raise ValueError('Raw row/cell mismatch')
    if cell!=current:
     if current is not None:computed.append(emit(current))
     current=cell;good=[];count=errors=0
    count+=1
    if row['error'] or row['status']!='200':errors+=1
    else:good.append({k:float(row[k]) for k in ['end_s','client_ms','es_took_ms','service_ms','queue_ms']})
  if current is not None:computed.append(emit(current))
 if len(computed)!=240:raise ValueError('Incomplete raw cells')
 checks=[]
 for x in computed:
  for key in ['requests','errors','throughput','p50_ms','p95_ms','es_p50_ms','es_p95_ms']:
   if not math.isclose(float(x[key]),float(meta[x['cell']][key]),abs_tol=1e-9,rel_tol=1e-12):checks.append({'cell':x['cell'],'field':key})
 perf=summary(computed,['p50_ms','p95_ms','throughput','errors','es_p50_ms','es_p95_ms']);components=summary(computed,['service_p50_ms','service_p95_ms','dispatch_p50_ms','dispatch_p95_ms'])
 keys=['path','scenario','config','clients','metric'];fields=['mean','sd','ci95_low','ci95_high']
 checks+=compare(perf,rows(original/'search_summary.csv'),keys,fields);checks+=compare(components,rows(original/'search_latency_components_summary.csv'),keys,fields)
 idx=rows(original/'indexing_raw.csv');groups=collections.defaultdict(list)
 for x in idx:
  if x['error']:raise ValueError('Incomplete indexing replicate')
  x['docs_s']=int(x['documents'])/float(x['duration_s']);groups[(x['mode'],x['analyzer'])].append(x)
 indexing=[];effects=[]
 for (mode,analyzer),items in groups.items():
  if len(items)!=5:raise ValueError('Indexing replicate count mismatch')
  for metric in ['duration_s','docs_s','store_bytes','bulk_errors']:
   v=[float(x[metric]) for x in items];lo,hi=ci(v);indexing.append(dict(mode=mode,analyzer=analyzer,replicates=5,metric=metric,mean=st.mean(v),sd=st.stdev(v),ci95_low=lo,ci95_high=hi))
 for mode in ['pipeline','preprocessed']:
  aa={x['replicate']:x for x in groups[(mode,'standard')]};bb={x['replicate']:x for x in groups[(mode,'italiano')]}
  for metric in ['duration_s','docs_s','store_bytes']:
   v=[float(bb[r][metric])-float(aa[r][metric]) for r in sorted(aa)];lo,hi=ci(v);effects.append(dict(mode=mode,contrast='italiano-standard',metric=metric,paired_replicates=5,difference=st.mean(v),ci95_low=lo,ci95_high=hi))
 checks+=compare(indexing,rows(original/'indexing_summary.csv'),['mode','analyzer','metric'],fields)
 checks+=compare(effects,rows(original/'indexing_effects.csv'),['mode','contrast','metric'],['difference','ci95_low','ci95_high'])
 se=[]
 for path in ['elasticsearch','flask_html']:
  for scenario in ['controlled','capacity']:
   for clients in [1,4,8,16]:
    for lo,hi in [('A','B'),('B','C')]:
     aa={x['replicate']:x for x in computed if (x['path'],x['scenario'],x['clients'],x['config'])==(path,scenario,clients,lo)};bb={x['replicate']:x for x in computed if (x['path'],x['scenario'],x['clients'],x['config'])==(path,scenario,clients,hi)}
     for metric in ['p50_ms','p95_ms','throughput']:
      v=[bb[r][metric]-aa[r][metric] for r in sorted(aa)];left,right=ci(v);se.append(dict(path=path,scenario=scenario,clients=clients,contrast=hi+'-'+lo,metric=metric,paired_replicates=5,difference=st.mean(v),ci95_low=left,ci95_high=right))
 checks+=compare(se,rows(original/'search_effects.csv'),['path','scenario','clients','contrast','metric'],['difference','ci95_low','ci95_high'])
 out.mkdir(parents=True,exist_ok=True)
 for name,data in [('search_summary.csv',perf),('search_latency_components_summary.csv',components),('indexing_summary.csv',indexing),('indexing_effects.csv',effects),('search_effects.csv',se)]:write(out/name,data)
 result={'recomputed_from_raw':True,'measured_requests':sum(x['requests'] for x in computed),'errors':sum(x['errors'] for x in computed),'cells':len(computed),'indexing_runs':len(idx),'sustainable_cells':sum(x['sustainable_observed'] for x in computed),'mismatches':checks,'passed':not checks,'absolute_tolerance':1e-9,'relative_tolerance':1e-12,'bootstrap_resamples':10000,'seed':SEED,'bootstrap_unit':'five experimental replicates, not requests','elasticsearch_calls':0}
 (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
 if checks:raise SystemExit(1)
if __name__=='__main__':main()
