"""Failure classification and meaningful checks of the read-only demo tool."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('demo_smoke', Path(__file__).parents[1] / 'scripts/demo_smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_unavailable_dependencies_are_not_reported_as_success(monkeypatch):
    class Offline:
        def info(self):
            raise ConnectionError('offline')
    def unavailable(*args, **kwargs):
        raise ConnectionError('offline')
    monkeypatch.setattr(smoke, 'urlopen', unavailable)
    report = smoke.run_checks(Offline(), 'missing', 'http://localhost', [{'id':'simple','params':{'q':'x'}}])
    assert report['summary']['FAIL'] == 2  # ES and HTTP availability
    assert report['summary']['PASS'] == 0
    assert report['summary']['SKIP'] > 0


@pytest.mark.parametrize('case,data', [
    ({'params':{'q':'x', 'category':'Italia'}}, {'total':1,'hits':[{'categories':['Francia']}]}),
    ({'params':{'q':'x', 'year':'2023'}}, {'total':1,'hits':[{'date':'2024-01-01'}]}),
    ({'params':{'q':'x', 'sort':'date'}}, {'total':2,'hits':[{'date':'2020-01-01'},{'date':'2024-01-01'}]}),
])
def test_smoke_rejects_wrong_filters_and_order(case, data):
    with pytest.raises(AssertionError):
        smoke.inspect_response(case, data)


def test_smoke_detects_count_and_title_drift():
    case = {'params':{'q':'x'}}
    data = {'total':1,'hits':[{'id':'1','title':'Titolo modificato'}]}
    with pytest.raises(AssertionError):
        smoke.inspect_response(case, data, {'total':2,'top3':[]})
    with pytest.raises(AssertionError):
        smoke.inspect_response(case, data, {'total':1,'top3':[{'id':'1','title':'Originale'}]})
