import copy,csv,hashlib,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ai_reproduction',ROOT/'reproduce.py');calc=importlib.util.module_from_spec(spec);spec.loader.exec_module(calc)
class Integrity(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='wikinews-integrity-');self.root=Path(self.temp.name);shutil.copytree(ROOT/'data',self.root/'data');self.private=calc.read(self.root/'data/ranking_private.json')
 def tearDown(self):self.temp.cleanup()
 def mutate_csv(self,fn):
  p=self.root/'data/qrels_gpt6.original.csv';data=calc.csvread(p);fn(data);calc.write(p,data)
 def test_complete_frozen_inputs(self):
  private,pool,labels=calc.validate(self.root);self.assertEqual((len(private['queries']),len(pool),len(labels)),(18,244,2))
 def test_duplicate_rejected(self):
  self.mutate_csv(lambda d:d.append(d[0].copy()))
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_missing_rejected(self):
  self.mutate_csv(lambda d:d.pop())
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_invalid_grade_rejected(self):
  self.mutate_csv(lambda d:d[0].update(grade='3'))
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_blank_grade_rejected(self):
  self.mutate_csv(lambda d:d[0].update(grade=''))
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_unknown_id_rejected(self):
  self.mutate_csv(lambda d:d[0].update(candidate_id='unknown'))
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_mixed_assessor_rejected(self):
  self.mutate_csv(lambda d:d[0].update(assessor='different'))
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_query_intent_mismatch_rejected(self):
  p=self.root/'data/queries.json';q=calc.read(p);q[0]['intent']='changed';calc.save(p,q)
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_rank_duplicate_rejected(self):
  r=self.private['rankings']['v01']['A'];r[1]=r[0];calc.save(self.root/'data/ranking_private.json',self.private)
  with self.assertRaises(ValueError):calc.validate(self.root)
 def test_manifest_tamper_rejected(self):
  p=self.root/'file';p.write_text('original');calc.save(self.root/'manifest.json',{'files':{'file':calc.sha(p)}});p.write_text('tampered')
  with self.assertRaises(ValueError):calc.verify_manifest(self.root)
 def test_qualitative_audit_is_not_qrels(self):
  p=self.root/'data/qualitative_audit_53.original.csv';d=calc.csvread(p);d[0]['grado_GPT6']='0';calc.write(p,d)
  with self.assertRaises(ValueError):calc.validate(self.root)
class Formulas(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.analysis=calc.original_analysis(ROOT)
 def test_metrics_known_example(self):
  m=self.analysis.metric(['a'],{'a':2});self.assertEqual(m,{'nDCG@10':1.,'P@5':.2,'MRR@10':1.})
 def test_no_relevant_and_short_ranking(self):
  self.assertEqual(self.analysis.metric([],{'a':0}),dict(zip(['nDCG@10','P@5','MRR@10'],[0.,0.,0.])))
 def test_quadratic_kappa(self):
  self.assertEqual(self.analysis.kappa([(0,0),(1,1),(2,2)]),1.)
  self.assertEqual(self.analysis.kappa([(0,2),(2,0)]),-1.)
  self.assertIsNone(self.analysis.kappa([(0,0)]))
 def test_group_resampling_is_deterministic(self):
  q=[{'id':'a','group':'g'},{'id':'b','group':'g'},{'id':'c','group':'h'}];v={'a':0.,'b':1.,'c':.5}
  self.assertEqual(calc.bootstrap(v,q,n=100),[.5,.5])
 def test_human_guard_remains_active(self):
  spec=importlib.util.spec_from_file_location('protected_human_tool',ROOT/'historical/human_ranking_analysis.py');human=importlib.util.module_from_spec(spec);spec.loader.exec_module(human)
  old=sys.argv
  try:
   sys.argv=['human_tool','--assessor1','missing1','--assessor2','missing2']
   with self.assertRaises(SystemExit) as failure:human.run()
   self.assertEqual(failure.exception.code,2)
  finally:sys.argv=old
 def test_original_annotations_immutable(self):
  sources=calc.read(ROOT/'SOURCE_ARCHIVES.json');records=[m for z in sources['sources'] for m in z['members'] if m['name'] in ['qrels_llm_only.csv','qrels_GPT6.csv','qrels_Claude_Opus55.csv']]
  self.assertEqual(len(records),3)
  for row in records:self.assertEqual(calc.sha(ROOT.parents[1]/row['published_path']),row['sha256'])
if __name__=='__main__':unittest.main()
