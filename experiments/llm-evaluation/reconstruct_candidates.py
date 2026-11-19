"""Rebuild original blind inputs from a checksum-verified official dump; no ES or LLM."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dump',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 ref=json.loads((ROOT/'data/corpus_reference.json').read_text(encoding='utf-8'))
 if sha(args.dump)!=ref['dump_sha256']:raise ValueError('Wrong dump SHA-256; current/live pages are not a substitute')
 repo=ROOT.parents[1]
 for name,digest in ref['original_parser_sha256'].items():
  portable=name.replace('\\','/')
  if portable in {'wikinews_search/parsing.py','wikinews_search/dump.py','wikinews_search/statistics.py'} and sha(repo/portable)!=digest:raise ValueError('Parser source differs from original: '+name)
 sys.path.insert(0,str(repo))
 from wikinews_search.dump import iter_records
 from wikinews_search.parsing import record_to_article
 private=json.loads((ROOT/'data/ranking_private.json').read_text(encoding='utf-8'));wanted=set(private['candidate_mapping'].values());articles={}
 for record in iter_records(args.dump):
  if str(record.get('identifier','')) in wanted:
   article=record_to_article(record)
   if article is not None:articles[article.id]=article # last valid duplicate wins, as in Bulk index
 if set(articles)!=wanted:raise ValueError('Missing source documents')
 rows=[]
 for line in (ROOT/'data/pool.metadata.jsonl').read_text(encoding='utf-8').splitlines():
  x=json.loads(line);doc=private['candidate_mapping'][x['query_id']+'|'+x['candidate_id']];a=articles[doc]
  if hashlib.sha256(a.body.encode()).hexdigest()!=x['body_sha256'] or len(a.body)!=x['body_chars'] or a.title!=x['title'] or a.url!=x['url']:raise ValueError('Reconstructed content differs: '+doc)
  ending='\r\n' if ref.get('original_line_ending')=='CRLF' else '\n'
  rows.append(json.dumps({key:a.body if key=='body' else x[key] for key in x['original_field_order']},ensure_ascii=False)+ending)
 payload=''.join(rows).encode();digest=hashlib.sha256(payload).hexdigest()
 if digest!=ref['original_blind_candidates_sha256']:raise ValueError('Original complete input checksum not reproduced')
 output=args.out.resolve()
 if output.is_relative_to(ROOT.resolve()) or output.exists():raise ValueError('Use a new output outside the published evaluation directory')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(payload)
 print(json.dumps({'pairs':len(rows),'distinct_documents':len(articles),'sha256':digest,'original_bytes_reconstructed':True,'output':str(output)}))
if __name__=='__main__':main()
