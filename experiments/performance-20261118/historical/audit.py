"""Post-run integrity audit. Does not generate measurements or judgments."""
import collections,csv,json,random
import benchmark as b
R=b.ROOT
def csvrows(name):
    with (R/name).open(encoding='utf-8-sig',newline='') as f: yield from csv.DictReader(f)
def main():
    checks={}; detail={}; cells=b.read('search_cells.json'); schedule=b.read('search_schedule.json'); w=b.read('workload.json')
    checks['240_cells_complete']=len(cells)==len(schedule)==240
    checks['cell_ids_unique_and_complete']={x['cell'] for x in cells}==set(range(1,241))
    checks['cell_metadata_matches_frozen_schedule']=all(all(x[k]==schedule[x['cell']-1][k] for k in ['path','scenario','config','clients','replicate']) for x in cells)
    qorder={}
    for rep in range(1,6):
        qq=list(w['queries']);random.Random(b.SEED+rep).shuffle(qq);qorder[rep]=qq
    counts=collections.Counter(); errors=collections.Counter(); seen=set(); previous=None; timing_ok=True; query_ok=True; sequence_ok=True; total=0
    events=[]; durations=0.; concurrency=[]; cellmap={x['cell']:x for x in cells}
    def concurrent(cell,events,duration):
        active=peak=0
        for timestamp,delta in sorted(events): active+=delta; peak=max(peak,active)
        x=cellmap[cell]
        return dict(cell=cell,path=x['path'],scenario=x['scenario'],replicate=x['replicate'],config=x['config'],configured_max_clients=x['clients'],observed_peak_inflight=peak,time_weighted_mean_inflight=duration/x['elapsed_s'])
    for x in csvrows('search_raw.csv'):
        c=int(x['cell']); sequence=int(x['sequence']); rep=int(x['replicate']); total+=1
        if c!=previous:
            if previous is not None:
                sequence_ok &= seen==set(range(counts[previous])); concurrency.append(concurrent(previous,events,durations))
            seen=set(); previous=c;events=[];durations=0.
        sequence_ok &= sequence not in seen; seen.add(sequence)
        counts[c]+=1; errors[c]+=bool(x['error']) or x['status']!='200'
        timing_ok &= float(x['end_s'])>=float(x['start_s']) and float(x['client_ms'])>=0 and float(x['service_ms'])>=0 and float(x['queue_ms'])>=0
        events.extend([(float(x['start_s']),1),(float(x['end_s']),-1)]);durations+=float(x['service_ms'])/1000
        query_ok &= x['query_id']==qorder[rep][sequence%len(qorder[rep])]['id']
    if previous is not None:
        sequence_ok &= seen==set(range(counts[previous]));concurrency.append(concurrent(previous,events,durations))
    b.rows('search_observed_concurrency.csv',concurrency)
    checks['capacity_peak_concurrency_matches_configured_clients']=all(x['observed_peak_inflight']==x['configured_max_clients'] for x in concurrency if x['scenario']=='capacity')
    checks['raw_counts_match_cells']=all(counts[x['cell']]==x['requests'] and errors[x['cell']]==x['errors'] for x in cells)
    checks['raw_sequence_unique_complete']=bool(sequence_ok)
    checks['raw_query_order_matches_seed']=bool(query_ok)
    checks['raw_timings_nonnegative_and_ordered']=bool(timing_ok)
    checks['controlled_96_requests_every_cell']=all(x['requests']==96 for x in cells if x['scenario']=='controlled')
    checks['five_replicates_each_condition']=all(len(g)==5 and {x['replicate'] for x in g}==set(range(1,6)) for g in [ [x for x in cells if (x['path'],x['scenario'],x['config'],x['clients'])==(p,s,k,c)] for p in ['elasticsearch','flask_html'] for s in ['controlled','capacity'] for k in b.CONFIGS for c in [1,4,8,16]])
    idx=list(csvrows('indexing_raw.csv'))
    checks['20_index_runs_complete']=len(idx)==20 and all(not x['error'] and int(x['operations'])==12257 and int(x['documents'])==12209 and int(x['bulk_errors'])==0 for x in idx)
    checks['20_unique_new_index_names']=len({x['index'] for x in idx})==20 and all(x['index'].startswith('wnbench_') for x in idx)
    checks['five_index_replicates_each_condition']=all(len([x for x in idx if x['mode']==mode and x['analyzer']==analyzer])==5 for mode in ['pipeline','preprocessed'] for analyzer in ['standard','italiano'])
    summary=list(csvrows('search_summary.csv')); isummary=list(csvrows('indexing_summary.csv'))
    checks['summary_units_are_five_runs']=len(summary)==288 and all(int(x['replicates'])==5 for x in summary) and len(isummary)==16 and all(int(x['replicates'])==5 for x in isummary)
    private=b.read('ranking_private.json'); public=[json.loads(x) for x in (R/'blind_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    expected={(qid,doc) for qid,configs in private['rankings'].items() for rank in configs.values() for doc in rank}
    checks['pool_union_deduplicated']=len(expected)==len(public)==len(private['candidate_mapping'])
    checks['pool_covers_exact_ranked_query_document_pairs']={(key.split('|')[0],doc) for key,doc in private['candidate_mapping'].items()}==expected
    checks['blind_fields_hide_rank_config_score']=all(set(x)=={'query_id','query','intent','candidate_id','title','url','body'} for x in public)
    for assessor in [1,2]:
        template=list(csvrows(f'annotation_assessor_{assessor}.csv'))
        checks[f'assessor_{assessor}_template_complete_and_unlabeled']=len(template)==len(public) and all(x['grade']==x['assessor']=='' for x in template) and len({(x['query_id'],x['candidate_id']) for x in template})==len(public)
    checks['frozen_workload_hash_matches']=b.sha(R/'workload.json')==b.read('manifest.json')['workload_sha256']
    checks['postflight_artifacts_present']=all((R/p).is_file() for p in ['all_index_corpus_verification.json','index_state_restoration.json','preexisting_indices_check.json','benchmark_index_metadata.json','postrun_workload_match_counts.csv','search_latency_components_summary.csv','blind_annotation.html','blind_assessor_package.zip'])
    checks['comparative_figures_present']=all((R/'figures'/f'{name}.{ext}').is_file() for name in ['elasticsearch','flask_html','indexing','controlled_effects','latency_components'] for ext in ['png','svg'])
    if (R/'index_state_restoration.json').exists():checks['new_index_open_closed_states_restored']=b.read('index_state_restoration.json')['restored']
    if (R/'preexisting_indices_check.json').exists(): checks['preexisting_index_uuids_and_counts_preserved']=all(x['uuid_unchanged'] and x['final_documents']==12209 for x in b.read('preexisting_indices_check.json').values())
    if (R/'benchmark_index_metadata.json').exists(): checks['all_new_indices_retained']=set(b.read('benchmark_index_metadata.json'))=={x['index'] for x in idx}
    if (R/'all_index_corpus_verification.json').exists():
        corpus=b.read('all_index_corpus_verification.json');checks['all_20_index_corpora_byte_equivalent_as_sources']=len(corpus)==20 and all(x['matches_search_corpus'] and x['documents']==12209 for x in corpus)
    if (R/'postrun_workload_match_counts.csv').exists():
        matches=list(csvrows('postrun_workload_match_counts.csv')); maps={(x['query_id'],x['config']):x for x in matches}
        checks['coverage_282_queries_completed']=len(matches)==282 and all(x['timed_out']=='False' and x['failed_shards']=='0' for x in matches)
        checks['B_C_matching_sets_have_equal_counts']=all(maps[(q['id'],'B')]['total_hits']==maps[(q['id'],'C')]['total_hits'] for q in w['queries'])
    detail.update(measured_requests=total,measured_errors=sum(errors.values()),index_runs=len(idx),validation_queries=len(private['queries']),validation_groups=len({q['group'] for q in private['queries']}),pooled_pairs=len(public),checks=checks,passed=all(checks.values()))
    b.save('audit.json',detail);print(json.dumps(detail,indent=2));raise SystemExit(0 if detail['passed'] else 1)
if __name__=='__main__':main()
