"""Independent comparison of two AI-only qrels; never claims human assessment.
Usage:
  python compare_llm_judges.py --archive results.zip --first qrels_llm_only.csv \
       --second qrels_second_llm.csv --out comparison_dir
"""
import argparse, collections, csv, json, random, math, statistics, zipfile, hashlib
from pathlib import Path

SEED=20261118
NBOOT=10000
METRICS=['nDCG@10','P@5','MRR@10']

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def save_csv(path,rows,fields=None):
    if not rows and not fields: return
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def percentile(sorted_values,p):
    return sorted_values[max(0,math.ceil(p*len(sorted_values))-1)] if sorted_values else None

def kappa(pairs,power=2):
    if not pairs: return None
    a=collections.Counter(x for x,y in pairs); b=collections.Counter(y for x,y in pairs); n=len(pairs)
    observed=sum((abs(x-y)/2)**power for x,y in pairs)/n
    expected=sum((abs(x-y)/2)**power*a[x]*b[y] for x in range(3) for y in range(3))/n**2
    return 1-observed/expected if expected else None

def metric(rank,j):
    def dcg(g): return sum((2**x-1)/math.log2(i+2) for i,x in enumerate(g))
    ideal=dcg(sorted(j.values(),reverse=True)[:10]); grades=[j[d] for d in rank[:10]]
    return {'nDCG@10':dcg(grades)/ideal if ideal else 0., 'P@5':sum(g>0 for g in grades[:5])/5,
            'MRR@10':next((1/i for i,g in enumerate(grades,1) if g>0),0.)}

def main():
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument('--archive',type=Path,required=True)
    pa.add_argument('--first',type=Path,required=True)
    pa.add_argument('--second',type=Path,required=True)
    pa.add_argument('--out',type=Path,required=True)
    arg=pa.parse_args();arg.out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(arg.archive) as z:
        private=json.loads(z.read('ranking_private.json'))
        blind=[json.loads(x) for x in z.read('blind_candidates.jsonl').decode('utf-8-sig').splitlines() if x.strip()]
    queries=private['queries']; qlookup={q['id']:q for q in queries}; rank=private['rankings']; mp=private['candidate_mapping']
    def load(path):
        data={}
        ass=set()
        for r in read_csv(path):
            assert r['query_id'] in qlookup, ('unknown query',r)
            k=r['query_id']+'|'+r['candidate_id']
            assert k in mp and k not in data, ('invalid key',k)
            assert r['grade'] in ('0','1','2'), ('invalid grade',k)
            assert r['assessor'].strip(), ('missing assessor',k)
            data[k]=r; ass.add(r['assessor'])
        assert set(data)==set(mp), ('incomplete',len(data),len(mp))
        assert len(ass)==1,ass
        return data, next(iter(ass))
    a,aid=load(arg.first); b,bid=load(arg.second)
    assert aid!=bid
    # Independent identity consistency across paired query forms, without relying on either judge for relevance.
    reverse=collections.defaultdict(list)
    for key,docid in mp.items():reverse[(qlookup[key.split('|')[0]]['group'],docid)].append(key)
    within=[]
    for jname,data in [('GPT-6',a),('Claude-Opus-5.5',b)]:
        for (grp,docid),keys in reverse.items():
            if len(keys)>1 and len({data[k]['grade'] for k in keys})>1:
                within.append({'judge':jname,'group':grp,'doc_id':docid,'keys':';'.join(keys),'grades':';'.join(data[k]['grade'] for k in keys)})
    save_csv(arg.out/'morphology_inconsistencies.csv',within,['judge','group','doc_id','keys','grades'])
    pairs=[(int(a[k]['grade']),int(b[k]['grade'])) for k in mp]
    confusion=[[sum(x==i and y==j for x,y in pairs) for j in range(3)] for i in range(3)]
    exact=sum(x==y for x,y in pairs)/len(pairs)
    binary=sum((x>0)==(y>0) for x,y in pairs)/len(pairs)
    weighted=kappa(pairs,2); linear=kappa(pairs,1)
    rng=random.Random(SEED); groups=collections.defaultdict(list)
    for q in queries:groups[q['group']].append(q['id'])
    keys_groups=list(groups)
    qbymap=collections.defaultdict(list)
    for k in mp:qbymap[k.split('|')[0]].append(k)
    kk=[]; ex=[]; binary_sample=[]
    for _ in range(NBOOT):
        gsample=rng.choices(keys_groups,k=len(keys_groups));p=[]
        for gr in gsample:
            for qid in groups[gr]:p.extend((int(a[k]['grade']),int(b[k]['grade'])) for k in qbymap[qid])
        val=kappa(p,2)
        if val is not None:kk.append(val)
        ex.append(sum(x==y for x,y in p)/len(p));binary_sample.append(sum((x>0)==(y>0) for x,y in p)/len(p))
    kci=[percentile(sorted(kk),.025),percentile(sorted(kk),.975)]
    eci=[percentile(sorted(ex),.025),percentile(sorted(ex),.975)]
    bci=[percentile(sorted(binary_sample),.025),percentile(sorted(binary_sample),.975)]

    judgments={}
    for jn,data in [('GPT-6',a),('Claude-Opus-5.5',b)]:
        j=collections.defaultdict(dict)
        for k,r in data.items():
            qid=k.split('|')[0]; j[qid][mp[k]]=int(r['grade'])
        for q in queries:
            expected=set().union(*[set(rank[q['id']][c]) for c in ('A','B','C')]);assert expected==set(j[q['id']]),(q['id'],expected-set(j[q['id']]))
        judgments[jn]=j
    measurements={jn:{q['id']:{c:metric(rank[q['id']][c],j[q['id']]) for c in ('A','B','C')} for q in queries} for jn,j in judgments.items()}
    def boots(qvals):
        rng=random.Random(SEED); samples=[]
        for _ in range(NBOOT):
            sampled=[qid for grp in rng.choices(keys_groups,k=len(keys_groups)) for qid in groups[grp]]
            samples.append(statistics.mean(qvals[qid] for qid in sampled))
        samples.sort();return (percentile(samples,.025),percentile(samples,.975))
    summary=[]; perquery=[]; contrasts=[]
    for judge,j in judgments.items():
        for q in queries:
            for c in ('A','B','C'):
                perquery.append({'judge':judge,'query_id':q['id'],'query':q['query'],'group':q['group'],'config':c,'no_relevant':not any(j[q['id']].values()),**measurements[judge][q['id']][c]})
            for hi,lo in [('B','A'),('C','B')]:
                contrasts.append({'judge':judge,'query_id':q['id'],'query':q['query'],'group':q['group'],'contrast':hi+'-'+lo,
                                 **{met:measurements[judge][q['id']][hi][met]-measurements[judge][q['id']][lo][met] for met in METRICS}})
        for met in METRICS:
            for c in ('A','B','C'):
                vals={q['id']:measurements[judge][q['id']][c][met] for q in queries}
                lo,hi=boots(vals)
                summary.append({'judge':judge,'metric':met,'comparison':c,'mean':statistics.mean(vals.values()),'ci95_low':lo,'ci95_high':hi,
                                'wins':'','ties':'','losses':''})
            for hi,lo in [('B','A'),('C','B')]:
                vals={q['id']:measurements[judge][q['id']][hi][met]-measurements[judge][q['id']][lo][met] for q in queries}
                a1,b1=boots(vals)
                summary.append({'judge':judge,'metric':met,'comparison':hi+'-'+lo,'mean':statistics.mean(vals.values()),'ci95_low':a1,'ci95_high':b1,
                                'wins':sum(x>0 for x in vals.values()),'ties':sum(x==0 for x in vals.values()),'losses':sum(x<0 for x in vals.values())})
    save_csv(arg.out/'ranking_summary_by_judge.csv',summary)
    save_csv(arg.out/'ranking_per_query_by_judge.csv',perquery)
    save_csv(arg.out/'ranking_contrasts_by_query.csv',contrasts)
    discrepancies=[]; allpairs=[]; bl={r['query_id']+'|'+r['candidate_id']:r for r in blind}
    assert set(bl)==set(mp)
    byq=[]
    for q in queries:
        rel=[k for k in mp if k.startswith(q['id']+'|')]
        disagree=sum(a[k]['grade']!=b[k]['grade'] for k in rel)
        byq.append({'query_id':q['id'],'query':q['query'],'category':q['category'],'group':q['group'],
                    'n':len(rel),'disagreements':disagree,'exact_agreement':(len(rel)-disagree)/len(rel),
                    'first_2':sum(a[k]['grade']=='2' for k in rel),'second_2':sum(b[k]['grade']=='2' for k in rel)})
    save_csv(arg.out/'agreement_by_query.csv',byq)
    for k in mp:
        entry=bl[k]
        row={'query_id':entry['query_id'],'query':entry['query'],'group':qlookup[entry['query_id']]['group'],'candidate_id':entry['candidate_id'],
             'title':entry['title'],'gpt6_grade':int(a[k]['grade']),'claude_grade':int(b[k]['grade']),
             'gpt6_note':a[k].get('note',''),'claude_note':b[k].get('note',''),'url':entry.get('url','')}
        allpairs.append(row)
        if a[k]['grade']!=b[k]['grade']: discrepancies.append(row)
    save_csv(arg.out/'all_244_pairs_side_by_side.csv',allpairs)
    save_csv(arg.out/'53_disagreements_to_review.csv',discrepancies,fields=list(allpairs[0]))
    effects_by_judge={}
    for judge in measurements:
        for contrast in ('B-A','C-B'):
            hi,lo=contrast.split('-')
            v={q['id']:measurements[judge][q['id']][hi]['nDCG@10']-measurements[judge][q['id']][lo]['nDCG@10'] for q in queries}
            effects_by_judge[(judge,contrast)]=v
    sensitivity=[]
    for judge in measurements:
        for contrast in ('B-A','C-B'):
            values=effects_by_judge[(judge,contrast)]
            for excl_name,ex in [('all',set()),('exclude_Brexit_v05',{'v05'}),('exclude_accents_v12_v13',{'v12','v13'}),('exclude_Brexit_and_accents',{'v05','v12','v13'})]:
                v=[val for qid,val in values.items() if qid not in ex]
                sensitivity.append({'judge':judge,'contrast':contrast,'condition':excl_name,'n_queries':len(v),'mean_delta_ndcg10':statistics.mean(v)})
    save_csv(arg.out/'sensitivity.csv',sensitivity)
    delta_judges=[]
    for contrast in ('B-A','C-B'):
        differences={q['id']:effects_by_judge[('Claude-Opus-5.5',contrast)][q['id']]-effects_by_judge[('GPT-6',contrast)][q['id']] for q in queries}
        lo,hi=boots(differences)
        delta_judges.append({'contrast':contrast,'difference_claude_minus_gpt6':statistics.mean(differences.values()),'ci95_low':lo,'ci95_high':hi})
    save_csv(arg.out/'cross_judge_effect_stability.csv',delta_judges)
    metadata={'source_first':str(arg.first),'source_second':str(arg.second),'sha256_first':hashlib.sha256(arg.first.read_bytes()).hexdigest(),
              'sha256_second':hashlib.sha256(arg.second.read_bytes()).hexdigest(),
              'source_rankings':'ranking_private.json in '+str(arg.archive),'run_count':len(queries),'n_groups':len(groups),
              'n_candidates':len(mp),'first_assessor_label':aid,'second_assessor_label':bid,'seed':SEED,'n_bootstrap':NBOOT,'human_confirmed':False}
    agreement={'metadata':metadata,'confusion_rows_GPT6_cols_Claude':confusion,'exact':exact,'exact_ci95_group_bootstrap':eci,
               'binary_agreement_relevant_grade_ge_1':binary,'binary_ci95_group_bootstrap':bci,
               'quadratic_weighted_kappa':weighted,'quadratic_kappa_ci95_group_bootstrap':kci,
               'linear_weighted_kappa':linear,'grades_first':dict(collections.Counter(int(r['grade']) for r in a.values())),
               'grades_second':dict(collections.Counter(int(r['grade']) for r in b.values())),
               'disagreements':len(discrepancies),'morphology_inconsistencies':within,
               'cross_judge_effect_stability':delta_judges}
    (arg.out/'agreement.json').write_text(json.dumps(agreement,ensure_ascii=False,indent=2),encoding='utf-8')
    def f(x):return f'{x:.4f}'
    mtable=[]
    for met in METRICS:
        for judge in measurements:
            cols=[next(x for x in summary if x['judge']==judge and x['metric']==met and x['comparison']==c) for c in ['A','B','C','B-A','C-B']]
            mtable.append('| '+judge+' | '+met+' | '+' | '.join(f(x['mean']) for x in cols)+' |')
    ef=[]
    for contrast in ('B-A','C-B'):
        for judge in measurements:
            obj=next(x for x in summary if x['judge']==judge and x['metric']=='nDCG@10' and x['comparison']==contrast)
            ef.append(f"| {judge} | {contrast} | {f(obj['mean'])} | [{f(obj['ci95_low'])}; {f(obj['ci95_high'])}] | {obj['wins']}/{obj['ties']}/{obj['losses']} |")
    biggest=sorted(byq,key=lambda x:x['disagreements'],reverse=True)
    l=[]
    l.extend(['# Confronto indipendente AI-only — GPT-6 e Claude Opus 5.5','',
              '**Natura del riferimento:** due serie di annotazioni LLM cieche; nessuna valutazione o conferma umana. Non è una ground truth umana.','',
              f'- Coppie validate: **{len(mp)}**, query **{len(queries)}**, gruppi **{len(groups)}**.','- Sono state confrontate le stesse 244 coppie tramite ID opachi; nessun documento mancante o duplicato.','',
              '## Concordanza sulle etichette','',
              f'- Accordo esatto: **{exact*100:.2f}%** ({len(mp)-len(discrepancies)}/{len(mp)}), IC95 bootstrap per gruppi [{eci[0]*100:.2f}%; {eci[1]*100:.2f}%].',
              f'- Kappa pesato quadratico: **{f(weighted)}**; IC95 [{f(kci[0])}; {f(kci[1])}].',
              f'- Kappa pesato lineare: **{f(linear)}**.',
              f'- Accordo binario rilevante/non rilevante (1/2 vs 0): **{binary*100:.2f}%**; IC95 [{bci[0]*100:.2f}%; {bci[1]*100:.2f}%].',
              f'- Disaccordi: **{len(discrepancies)}**, di cui {sum(abs(x-y)==2 for x,y in pairs)} di due livelli.',
              '- Matrice di confusione (righe GPT-6, colonne Claude; classi 0,1,2):',
              '', '| GPT-6 \\ Claude | 0 | 1 | 2 |','|---|---:|---:|---:|',
              *[f'| {i} | '+ ' | '.join(str(v) for v in row)+' |' for i,row in enumerate(confusion)],
              '',
              '## Metriche del ranking basate sulle etichette di ciascun giudice','',
              '| Giudice | Metrica | A | B | C | B−A | C−B |','|---|---|---:|---:|---:|---:|---:|',*mtable,'',
              '**Metrica primaria:** nDCG@10. P@5 e MRR@10 sono secondarie; nDCG usa IDCG limitato al pool A/B/C top-10, non il corpus intero.','',
              '### Confronti appaiati per nDCG@10','',
              '| Giudice | Contrasto | Differenza media | IC 95% bootstrap per gruppi | Vittorie/pari/sconfitte |',
              '|---|---|---:|---|---|',*ef,'',
              '### Analisi di sensibilità per nDCG@10','',
              '| Giudice | Contrasto | Tutte | Senza Brexit v05 | Senza accenti v12/v13 |',
              '|---|---|---:|---:|---:|',
              *[f"| {judge} | {con} | {f(next(x['mean_delta_ndcg10'] for x in sensitivity if x['judge']==judge and x['contrast']==con and x['condition']=='all'))} | {f(next(x['mean_delta_ndcg10'] for x in sensitivity if x['judge']==judge and x['contrast']==con and x['condition']=='exclude_Brexit_v05'))} | {f(next(x['mean_delta_ndcg10'] for x in sensitivity if x['judge']==judge and x['contrast']==con and x['condition']=='exclude_accents_v12_v13'))} |" for judge in measurements for con in ('B-A','C-B')],
              '',
              '## Dove i due LLM dissentono di più','',
              '| Query | Descrizione | Discordanti / totale |', '|---|---|---:|',
              *[f"| {x['query_id']} | {x['query']} | {x['disagreements']}/{x['n']} |" for x in biggest[:7]],
              '',
              f"Controllo di coerenza sui documenti ripetuti nelle coppie flessive/accentuali: **{len(within)}** contraddizioni interne.",
              '',
              '## Interpretazione e limiti','',
              '- Le due annotazioni sono state assegnate a modelli differenti e non sono state fornite a Claude le etichette GPT-6; il confronto è AI-only.',
              '- Claude ha dichiarato una lettura selettiva dei documenti molto lunghi (introduzione e passaggi pertinenti), non integrale: possibile limite delle annotazioni.',
              '- I due modelli non coincidono perfettamente nel criterio 1 vs 2; una media dei due gradi non sarebbe una adjudication indipendente.',
              '- Gli IC sono bootstrap per 15 gruppi di query, non incorporano errori sistematici dei modelli o differenze nella lettura.',
              '- Query e intenti sintetici non sono campionati da log utenti; l’accordo AI non prova la correttezza rispetto a un giudice umano.',
              '- Il benchmark usa un pool top-10 e non può stimare recall dell’intero corpus.',
              '- Le metriche vanno presentate separatamente per giudice; non usare --human-confirmed.',
              '', '## Provenienza e riproducibilità', '',
              f"- GPT-6 qrels SHA256: `{metadata['sha256_first']}`",
              f"- Claude qrels SHA256: `{metadata['sha256_second']}`",
              f'- Bootstrap: {NBOOT} ricampionamenti appaiati con seed {SEED}; unità di ricampionamento: gruppo di query.',
              '- Fonte ranking congelati: `results.zip/ranking_private.json`; nessun indice è stato ricalcolato.',
              '- I CSV e lo script `compare_llm_judges.py` sono conservati insieme al rapporto.',
              ''])
    (arg.out/'COMPARISON_REPORT.md').write_text('\n'.join(l),encoding='utf-8')
    print(json.dumps({'agreement':{'exact':exact,'quad_kappa':weighted,'linear_kappa':linear,'binary':binary,'ci_quad':kci,'ci_exact':eci},
                      'rankings':{judge:{met:{c:next(x['mean'] for x in summary if x['judge']==judge and x['metric']==met and x['comparison']==c) for c in ['A','B','C','B-A','C-B']} for met in METRICS} for judge in measurements},
                      'consistency_issues':len(within),'sensitivity':sensitivity},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
