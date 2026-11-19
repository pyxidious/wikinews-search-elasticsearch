"""Offline AI-only analysis of immutable qrels. Never invokes a model or Elasticsearch."""
from __future__ import annotations
import argparse,collections,csv,hashlib,importlib.util,json,math,random,statistics,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SEED=20261118
NBOOT=10000
TOL=1e-12
JUDGES={'GPT-6':'qrels_gpt6.original.csv','Claude-Opus-5.5':'qrels_claude.original.csv'}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def csvread(path):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,items,fields=None):
 items=list(items)
 with Path(path).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(items[0]));w.writeheader();w.writerows(items)
def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def original_analysis(root=ROOT):
 spec=importlib.util.spec_from_file_location('historical_ai_comparison',root/'historical/compare_llm_judges.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def verify_manifest(root):
 manifest=read(root/'manifest.json');bad=[]
 for name,expected in manifest['files'].items():
  path=(root/name).resolve()
  if not path.is_relative_to(root.resolve()) or not path.is_file() or sha(path)!=expected:bad.append(name)
 if bad:raise ValueError('Manifest mismatch: '+repr(bad))
 return len(manifest['files'])
def load_qrels(path,expected):
 data={};identities=set()
 for row in csvread(path):
  key=(row.get('query_id',''),row.get('candidate_id',''))
  if key not in expected or key in data:raise ValueError('Extraneous/duplicate ID: '+repr(key))
  if row.get('grade') not in {'0','1','2'} or not row.get('assessor','').strip():raise ValueError('Invalid/incomplete label: '+repr(key))
  data[key]=row;identities.add(row['assessor'].strip())
 if set(data)!=expected or len(identities)!=1:raise ValueError('Missing labels or mixed assessor identities')
 return data
def validate(root=ROOT):
 private=read(root/'data/ranking_private.json');queries=read(root/'data/queries.json')
 if private['queries']!=queries:raise ValueError('Query/intents differ between inputs')
 qids=[q['id'] for q in queries]
 if len(qids)!=18 or len(set(qids))!=18 or set(private['rankings'])!=set(qids):raise ValueError('Query coverage mismatch')
 if len({q['group'] for q in queries})!=15:raise ValueError('Group definition mismatch')
 public=[json.loads(line) for line in (root/'data/pool.metadata.jsonl').read_text(encoding='utf-8').splitlines()]
 expected={(q,c) for q,c in (k.split('|') for k in private['candidate_mapping'])}
 if len(expected)!=244 or {(x['query_id'],x['candidate_id']) for x in public}!=expected or len(public)!=244:raise ValueError('Pool keys mismatch/duplicates')
 qmap={q['id']:q for q in queries};ranked=set()
 for qid,configs in private['rankings'].items():
  if set(configs)!=set('ABC'):raise ValueError('Missing configuration')
  for rank in configs.values():
   if len(rank)>10 or len(set(rank))!=len(rank):raise ValueError('Invalid ranking depth or duplicates')
   ranked.update((qid,d) for d in rank)
 mapped={(key.split('|')[0],doc) for key,doc in private['candidate_mapping'].items()}
 if ranked!=mapped:raise ValueError('Pool does not equal deduplicated top-10 union')
 for row in public:
  if row['query']!=qmap[row['query_id']]['query'] or row['intent']!=qmap[row['query_id']]['intent'] or 'body' in row:raise ValueError('Metadata mismatch/full text unexpectedly published')
 labels={name:load_qrels(root/'data'/file,expected) for name,file in JUDGES.items()}
 if len({next(iter(rows.values()))['assessor'] for rows in labels.values()})!=2:raise ValueError('Assessor identity collision')
 disagreements={key for key in expected if labels['GPT-6'][key]['grade']!=labels['Claude-Opus-5.5'][key]['grade']}
 qualitative=csvread(root/'data/qualitative_audit_53.original.csv')
 if len(qualitative)!=53 or {(x['query_id'],x['candidate_id']) for x in qualitative}!=disagreements:raise ValueError('Qualitative audit does not cover exact disagreements')
 pool={(x['query_id'],x['candidate_id']):x for x in public}
 for row in qualitative:
  key=(row['query_id'],row['candidate_id']);p=pool[key]
  if row['grado_GPT6']!=labels['GPT-6'][key]['grade'] or row['grado_Claude']!=labels['Claude-Opus-5.5'][key]['grade'] or row['text_sha256']!=p['body_sha256'] or row['titolo']!=p['title']:raise ValueError('Qualitative audit inconsistent with frozen data')
 return private,public,labels
def bootstrap(values,queries,n=NBOOT):
 groups=collections.defaultdict(list)
 for q in queries:groups[q['group']].append(q['id'])
 rng=random.Random(SEED);samples=[]
 for _ in range(n):
  ids=[qid for g in rng.choices(list(groups),k=len(groups)) for qid in groups[g]]
  samples.append(statistics.mean(values[qid] for qid in ids))
 samples.sort();return [samples[math.ceil(.025*n)-1],samples[math.ceil(.975*n)-1]]
def extra_analyses(root,out,private,labels,analysis,np):
 queries=private['queries'];rankings=private['rankings'];mp=private['candidate_mapping'];sensitivity=[];loo=[];noacc=[];gpt_sensitivity={}
 conditions=[('all',set()),('exclude_Brexit_v05',{'v05'}),('exclude_accents_v12_v13',{'v12','v13'}),('exclude_Brexit_and_accents',{'v05','v12','v13'})]
 variants=[('original',lambda x:x),('partial_as_zero',lambda x:0 if x==1 else x),('partial_as_two',lambda x:2 if x==1 else x)]
 no_relevant={}
 for judge,data in labels.items():
  judgments=collections.defaultdict(dict)
  for (qid,cid),row in data.items():judgments[qid][mp[qid+'|'+cid]]=int(row['grade'])
  no_relevant[judge]=[q['id'] for q in queries if not any(judgments[q['id']].values())]
  original={}
  for variant,transform in variants:
   jj={q:{d:transform(g) for d,g in docs.items()} for q,docs in judgments.items()}
   per={q['id']:{c:analysis.metric(rankings[q['id']][c],jj[q['id']]) for c in 'ABC'} for q in queries}
   if variant=='original':original=per
   for condition,exclude in conditions if variant=='original' else [('all',set())]:
    subset=[q for q in queries if q['id'] not in exclude];table={}
    for metric in analysis.METRICS:
     means={c:statistics.mean(per[q['id']][c][metric] for q in subset) for c in 'ABC'}
     table[metric]={**means,'B_minus_A':statistics.mean(per[q['id']]['B'][metric]-per[q['id']]['A'][metric] for q in subset),'C_minus_B':statistics.mean(per[q['id']]['C'][metric]-per[q['id']]['B'][metric] for q in subset)}
     for hi,lo in [('B','A'),('C','B')]:
      values={q['id']:per[q['id']][hi][metric]-per[q['id']][lo][metric] for q in subset};ci=bootstrap(values,subset)
      sensitivity.append(dict(judge=judge,variant=variant,condition=condition,metric=metric,contrast=hi+'-'+lo,n_queries=len(subset),n_groups=len({q['group'] for q in subset}),mean=statistics.mean(values.values()),ci95_low=ci[0],ci95_high=ci[1]))
    if judge=='GPT-6':
     key={'all':'primary','exclude_Brexit_v05':'without_Brexit_query_v05','exclude_accents_v12_v13':'without_accent_group_v12_v13','exclude_Brexit_and_accents':'without_Brexit_and_accent_group'}[condition] if variant=='original' else {'partial_as_zero':'label_1_treated_as_0','partial_as_two':'label_1_treated_as_2'}[variant]
     gpt_sensitivity[key]=table
  for hi,lo in [('B','A'),('C','B')]:
   values={q['id']:original[q['id']][hi]['nDCG@10']-original[q['id']][lo]['nDCG@10'] for q in queries}
   for group in dict.fromkeys(q['group'] for q in queries):
    sub=[values[q['id']] for q in queries if q['group']!=group]
    loo.append(dict(giudice=judge,contrasto=hi+'-'+lo,gruppo_escluso=group,n_query_rimanenti=len(sub),delta_ndcg_rimanente=statistics.mean(sub),delta_completo=statistics.mean(values.values())))
   qs=[q for q in queries if q['group']!='accenti_0'];groups=list(dict.fromkeys(q['group'] for q in qs));by={g:np.array([values[q['id']] for q in qs if q['group']==g]) for g in groups};rng=np.random.default_rng(SEED)
   draws=[np.concatenate([by[g] for g in rng.choice(groups,size=len(groups),replace=True)]).mean() for _ in range(NBOOT)];low,high=np.quantile(draws,[.025,.975],method='linear')
   noacc.append(dict(giudice=judge,contrasto=hi+'-'+lo,esperimento='escluso gruppo accenti_0 (v12/v13)',query_rimanenti=len(qs),gruppi_rimanenti=len(groups),delta_ndcg=statistics.mean(values[q['id']] for q in qs),bootstrap_IC95_basso=float(low),bootstrap_IC95_alto=float(high),B_10000='seed=20261118'))
 write(out/'sensitivity_extended.csv',sensitivity);write(out/'leave_one_group_out.csv',loo);write(out/'bootstrap_senza_accenti.csv',noacc);save(out/'gpt6_sensitivity.json',gpt_sensitivity);save(out/'queries_without_relevant_in_pool.json',no_relevant)
 # Qualitative classifications are fixed analyst outputs, not inferred anew or used as qrels.
 audit=csvread(root/'data/qualitative_audit_53.original.csv');counts=collections.Counter(x['categoria_diagnostica'] for x in audit)
 save(out/'qualitative_audit_validation.json',{'pairs':len(audit),'distinct_titles':len({x['titolo'] for x in audit}),'category_counts':dict(counts),'new_judgments_generated':False,'human_adjudication':False})
def compare_references(root,out):
 mismatches=[];checked=0
 def near(label,a,b):
  nonlocal checked
  checked+=1
  if not math.isclose(float(a),float(b),rel_tol=TOL,abs_tol=TOL):mismatches.append({'field':label,'reference':a,'recalculated':b})
 for name,keys,fields in [
  ('ranking_summary_by_judge.csv',['judge','metric','comparison'],['mean','ci95_low','ci95_high']),
  ('cross_judge_effect_stability.csv',['contrast'],['difference_claude_minus_gpt6','ci95_low','ci95_high']),
  ('leave_one_group_out.csv',['giudice','contrasto','gruppo_escluso'],['delta_ndcg_rimanente','delta_completo']),
  ('bootstrap_senza_accenti.csv',['giudice','contrasto'],['delta_ndcg','bootstrap_IC95_basso','bootstrap_IC95_alto'])]:
  actual={tuple(row[k] for k in keys):row for row in csvread(out/name)};reference=csvread(root/'references'/name)
  if len(actual)!=len(reference):mismatches.append({'file':name,'reason':'row count mismatch'})
  for row in reference:
   key=tuple(row[k] for k in keys)
   if key not in actual:mismatches.append({'file':name,'key':key});continue
   for field in fields:near(name+str(key)+field,row[field],actual[key][field])
 ref=read(root/'references/agreement.json');now=read(out/'agreement.json')
 for field in ['exact','binary_agreement_relevant_grade_ge_1','quadratic_weighted_kappa','linear_weighted_kappa','disagreements']:near(field,ref[field],now[field])
 for field in ['exact_ci95_group_bootstrap','binary_ci95_group_bootstrap','quadratic_kappa_ci95_group_bootstrap']:
  for i in range(2):near(field+str(i),ref[field][i],now[field][i])
 if ref['confusion_rows_GPT6_cols_Claude']!=now['confusion_rows_GPT6_cols_Claude']:mismatches.append({'field':'confusion matrix'})
 def nested(a,b,prefix=''):
  for k,v in a.items():
   if isinstance(v,dict):nested(v,b[k],prefix+'/'+k)
   else:near(prefix+'/'+k,v,b[k])
 nested(read(root/'references/gpt6_sensitivity.json'),read(out/'gpt6_sensitivity.json'))
 # Also verify the published sensitivity table of the two-model comparison.
 ext=csvread(out/'sensitivity_extended.csv')
 for row in csvread(root/'references/sensitivity.csv'):
  found=next(x for x in ext if x['judge']==row['judge'] and x['contrast']==row['contrast'] and x['condition']==row['condition'] and x['variant']=='original' and x['metric']=='nDCG@10')
  near('sensitivity'+str(row),row['mean_delta_ndcg10'],found['mean'])
 result={'numeric_values_checked':checked,'absolute_tolerance':TOL,'relative_tolerance':TOL,'mismatches':mismatches,'passed':not mismatches,'references_used_as_inputs_to_metrics':False}
 save(out/'verification.json',result)
 if mismatches:raise ValueError('Recalculated/reference discrepancies; see verification.json')
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();root=args.root.resolve();out=args.out.resolve()
 if out.is_relative_to(root):parser.error('Output must be outside the frozen publication directory')
 verify_manifest(root);private,pool,labels=validate(root)
 try:import numpy as np
 except ImportError:parser.error('NumPy is needed to reproduce the separately documented historical post-hoc audit; see requirements-reproduction.txt')
 out.mkdir(parents=True,exist_ok=True);analysis=original_analysis(root)
 # Original AI-only calculator consumes a ZIP; build a transient adapter from published metadata, without article bodies.
 with tempfile.TemporaryDirectory(prefix='wikinews-ai-compute-') as temp:
  bundle=Path(temp)/'inputs.zip'
  with zipfile.ZipFile(bundle,'w') as z:
   z.writestr('ranking_private.json',json.dumps(private,ensure_ascii=False));z.writestr('blind_candidates.jsonl','\n'.join(json.dumps(x,ensure_ascii=False) for x in pool)+'\n')
  previous=sys.argv
  try:
   sys.argv=['compare_llm_judges.py','--archive',str(bundle),'--first',str(root/'data'/JUDGES['GPT-6']),'--second',str(root/'data'/JUDGES['Claude-Opus-5.5']),'--out',str(out)];analysis.main()
  finally:sys.argv=previous
 agreement=read(out/'agreement.json');agreement['metadata'].update(source_first='data/'+JUDGES['GPT-6'],source_second='data/'+JUDGES['Claude-Opus-5.5'],source_rankings='data/ranking_private.json; shared by both judges',human_confirmed=False)
 save(out/'agreement.json',agreement)
 extra_analyses(root,out,private,labels,analysis,np);verification=compare_references(root,out)
 save(out/'computation_environment.json',{'python':sys.version,'numpy':np.__version__,'historical_numpy_version':'non registrato','seed':SEED,'bootstrap':NBOOT,'human_confirmed':False,'annotation_model_calls':0,'elasticsearch_calls':0})
 print(json.dumps({'verified':verification,'human_confirmed':False},indent=2))
if __name__=='__main__':main()
