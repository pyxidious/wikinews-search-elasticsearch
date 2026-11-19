"""Strict human judgment analysis. No automatic labels. Standard library only."""
import argparse, collections, csv, json, math, random, statistics as st
from pathlib import Path
SEED=20261118
METRICS=['nDCG@10','P@5','MRR@10']
def metric(rank,j):
    def dcg(g): return sum((2**x-1)/math.log2(i+2) for i,x in enumerate(g))
    ideal=dcg(sorted(j.values(),reverse=True)[:10])
    return {'nDCG@10':dcg([j[d] for d in rank[:10]])/ideal if ideal else 0.,'P@5':sum(j[d]>0 for d in rank[:5])/5,'MRR@10':next((1/i for i,d in enumerate(rank[:10],1) if j[d]>0),0.)}
def load(path,private):
    expected=set(private['candidate_mapping']); judgments=collections.defaultdict(dict); seen=set(); identities=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=row['query_id']+'|'+row['candidate_id']
            if key not in expected or key in seen or row['grade'] not in ['0','1','2'] or not row['assessor'].strip(): raise ValueError('Judgment missing, duplicate, extraneous or assessor blank: '+key)
            seen.add(key); identities.add(row['assessor'].strip()); judgments[row['query_id']][private['candidate_mapping'][key]]=int(row['grade'])
    if seen!=expected: raise ValueError('All pooled candidates must be judged; missing='+str(len(expected-seen)))
    if len(identities)!=1: raise ValueError('Each judgment file must identify exactly one assessor or adjudication panel')
    return judgments
def kappa(pairs,power=2):
    if not pairs: return None
    a=collections.Counter(x for x,y in pairs); b=collections.Counter(y for x,y in pairs); n=len(pairs)
    observed=sum((abs(x-y)/2)**power for x,y in pairs)/n
    expected=sum((abs(x-y)/2)**power*a[x]*b[y]/n**2 for x in range(3) for y in range(3))
    return 1-observed/expected if expected else None
def bootstrap(values,queries,iterations=10000):
    groups=collections.defaultdict(list)
    for q in queries: groups[q['group']].append(q['id'])
    keys=list(groups); rng=random.Random(SEED); samples=[]
    for _ in range(iterations):
        ids=[qid for g in rng.choices(keys,k=len(keys)) for qid in groups[g]]
        samples.append(st.mean(values[q] for q in ids))
    samples.sort(); return [samples[math.ceil(.025*iterations)-1],samples[math.ceil(.975*iterations)-1]]
def write(path,rr):
    if not rr: return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0])); w.writeheader(); w.writerows(rr)
def analyze(private,j,out,prefix):
    queries=private['queries']; ranks=private['rankings']; per=[]; metrics={}
    for k in ['A','B','C']:
        metrics[k]={q['id']:metric(ranks[q['id']][k],j[q['id']]) for q in queries}
        for q in queries: per.append(dict(query_id=q['id'],group=q['group'],config=k,no_relevant=not any(j[q['id']].values()),**metrics[k][q['id']]))
    write(out/(prefix+'_per_query.csv'),per); contrasts=[]
    for a,b in [('A','B'),('B','C')]:
        for q in queries: contrasts.append(dict(query_id=q['id'],group=q['group'],contrast=b+'-'+a,**{m:metrics[b][q['id']][m]-metrics[a][q['id']][m] for m in METRICS}))
    write(out/(prefix+'_paired_differences.csv'),contrasts)
    summary=[]
    for m in METRICS:
        for k in ['A','B','C']:
            v={q['id']:metrics[k][q['id']][m] for q in queries}; low,high=bootstrap(v,queries)
            nonzero=[v[q['id']] for q in queries if any(j[q['id']].values())]
            summary.append(dict(metric=m,primary=m=='nDCG@10',estimate=k,mean=st.mean(v.values()),ci95_low=low,ci95_high=high,queries=len(v),groups=len({q['group'] for q in queries}),mean_excluding_no_relevant=st.mean(nonzero) if nonzero else None,wins='',ties='',losses=''))
        for a,b in [('A','B'),('B','C')]:
            v={q['id']:metrics[b][q['id']][m]-metrics[a][q['id']][m] for q in queries}; low,high=bootstrap(v,queries)
            summary.append(dict(metric=m,primary=m=='nDCG@10',estimate=b+'-'+a,mean=st.mean(v.values()),ci95_low=low,ci95_high=high,queries=len(v),groups=len({q['group'] for q in queries}),mean_excluding_no_relevant='',wins=sum(x>0 for x in v.values()),ties=sum(x==0 for x in v.values()),losses=sum(x<0 for x in v.values())))
    write(out/(prefix+'_summary.csv'),summary)
    (out/(prefix+'_no_relevant.json')).write_text(json.dumps([q['id'] for q in queries if not any(j[q['id']].values())],indent=2))
def run():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent); p.add_argument('--assessor1',type=Path,required=True); p.add_argument('--assessor2',type=Path,required=True); p.add_argument('--adjudicated',type=Path); p.add_argument('--human-confirmed',action='store_true',help='Operator attests input was independently completed by human assessors'); args=p.parse_args()
    if not args.human_confirmed: p.error('Human provenance must be explicitly confirmed; AI-assisted judgments are exploratory only.')
    private=json.loads((args.root/'ranking_private.json').read_text(encoding='utf-8')); a=load(args.assessor1,private); b=load(args.assessor2,private)
    def identity(path):
        with path.open(encoding='utf-8-sig',newline='') as f: return next(csv.DictReader(f))['assessor'].strip()
    if identity(args.assessor1)==identity(args.assessor2): p.error('Two distinct independent assessor identifiers are required')
    out=args.root/'human_analysis'; out.mkdir(exist_ok=True)
    queries=private['queries']; groups=collections.defaultdict(list)
    for q in queries: groups[q['group']].append(q['id'])
    pairs=[(a[q][d],b[q][d]) for q in a for d in a[q]]; rng=random.Random(SEED); samples=[]
    for _ in range(10000):
        pp=[(a[q][d],b[q][d]) for g in rng.choices(list(groups),k=len(groups)) for q in groups[g] for d in a[q]]
        k=kappa(pp)
        if k is not None: samples.append(k)
    samples.sort(); confusion=[[sum(x==i and y==j for x,y in pairs) for j in range(3)] for i in range(3)]
    agreement=dict(quadratic_weighted_kappa=kappa(pairs),linear_weighted_kappa=kappa(pairs,1),exact_agreement=sum(x==y for x,y in pairs)/len(pairs),n=len(pairs),confusion_matrix=confusion,quadratic_kappa_ci95=[samples[math.ceil(.025*len(samples))-1],samples[math.ceil(.975*len(samples))-1]] if samples else None,bootstrap_unit='predefined query groups',seed=SEED,bootstrap_requested_resamples=10000,bootstrap_defined_resamples=len(samples),bootstrap_undefined_resamples=10000-len(samples))
    (out/'agreement.json').write_text(json.dumps(agreement,indent=2))
    analyze(private,a,out,'assessor1'); analyze(private,b,out,'assessor2')
    if args.adjudicated: analyze(private,load(args.adjudicated,private),out,'adjudicated')
    write(out/'disagreements.csv',[dict(query_id=q,document_id=d,assessor1=a[q][d],assessor2=b[q][d]) for q in a for d in a[q] if a[q][d]!=b[q][d]])
if __name__=='__main__': run()
