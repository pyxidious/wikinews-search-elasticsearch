"""Method tests use tiny artificial examples, never experimental ranking labels."""
import json, math, tempfile, unittest
from pathlib import Path
import benchmark as b
import ranking_analysis as r
class Methods(unittest.TestCase):
    def test_payload(self):
        for k in b.CONFIGS:
            x=b.body('test',k)
            self.assertNotIn('body',x['source']); self.assertIn('highlight',x); self.assertIn('aggs',x)
            self.assertEqual(x['query']['bool']['must'][0]['simple_query_string']['fields'],b.CONFIGS[k][1])
    def test_exact_metrics(self):
        self.assertEqual(r.metric(['a'],{'a':2}),{'nDCG@10':1.,'P@5':.2,'MRR@10':1.})
        v=r.metric(['b','a'],{'a':2,'b':0}); self.assertAlmostEqual(v['nDCG@10'],1/math.log2(3)); self.assertEqual(v['MRR@10'],.5)
    def test_no_relevant(self): self.assertEqual(r.metric(['a'],{'a':0}),dict(zip(r.METRICS,[0.,0.,0.])))
    def test_short_precision_denominator(self): self.assertEqual(r.metric(['a','b'],{'a':1,'b':1})['P@5'],.4)
    def test_kappa(self):
        self.assertEqual(r.kappa([(0,0),(1,1),(2,2)]),1.)
        self.assertIsNone(r.kappa([(0,0)]))
        self.assertAlmostEqual(r.kappa([(0,2),(2,0)]),-1.)
    def test_bootstrap_group_constant(self):
        self.assertEqual(r.bootstrap({'a':1,'b':1},[dict(id='a',group='g'),dict(id='b',group='g')],100),[1.,1.])
    def test_workload_frozen(self):
        w=b.read('workload.json'); m=b.read('manifest.json')
        self.assertEqual(b.sha(b.ROOT/'workload.json'),m['workload_sha256']); self.assertEqual(len(w['queries']),94); self.assertEqual(len(w['validation']),18)
    def test_unjudged_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'q.csv'; p.write_text('query_id,candidate_id,grade,assessor,note\nv01,x,,,\n')
            with self.assertRaises(ValueError): r.load(p,{'candidate_mapping':{'v01|x':'doc'}})
    def test_schedule(self):
        cells=b.read('search_schedule.json'); self.assertEqual(len(cells),240)
        for rep in range(1,6): self.assertEqual(len([c for c in cells if c['replicate']==rep]),48)
if __name__=='__main__':
    import sys
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Methods)
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
