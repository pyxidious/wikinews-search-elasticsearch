import csv
import json
import math
from types import SimpleNamespace

import pytest

from wikinews_search.evaluation import CONFIGS, INDICES, evaluate, metrics, percentile, pool, prepare, save
from wikinews_search.indexer import MAPPINGS
from .fakes import RESPONSE


def test_metrics_known_order_and_no_relevant():
    result = metrics(["b", "a", "c"], {"a": 2, "b": 0, "c": 1})
    assert result["P@5"] == .4 and result["MRR@10"] == .5
    assert result["nDCG@10"] == pytest.approx((3 / math.log2(3) + .5) / (3 + 1 / math.log2(3)))
    assert metrics([], {"a": 1}) == {"P@5": 0, "MRR@10": 0, "nDCG@10": 0}
    assert metrics(["a"], {"a": 0})["nDCG@10"] == 0
    assert percentile(list(range(1, 21)), .95) == 19


def test_pool_and_manual_judgments_workflow(tmp_path):
    queries = [{"id": "q1", "query": "Roma", "intent": "Citta di Roma"}]
    save(tmp_path / "manifest.json", {"indices": {a: {"uuid": a} for a in INDICES}})
    calls = []
    def get(index):
        analyzer = next(a for a, name in INDICES.items() if name == index)
        return {index: {"settings": {"index": {"uuid": analyzer}}}}
    def search(**kw):
        calls.append(kw)
        return RESPONSE
    es = SimpleNamespace(indices=SimpleNamespace(get=get), search=search)
    pool(es, queries, tmp_path, repeats=2)
    assert len(calls) == 9
    assert {c["index"] for c in calls} == set(INDICES.values())
    assert all(name != "itwikinews" for name in INDICES.values())
    assert len((tmp_path / "candidates.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(ValueError, match="incompleto"):
        evaluate(tmp_path, tmp_path / "qrels-template.csv")
    qrels = tmp_path / "qrels.csv"
    qrels.write_text("query_id,document_id,grade,assessor,note\nq1,1002,2,studente,letto\n", encoding="utf-8")
    result = evaluate(tmp_path, qrels)
    assert set(result["configs"]) == set(CONFIGS)
    assert result["configs"]["C"]["mean"]["P@5"] == .2
    qrels.write_text("query_id,document_id,grade,assessor,note\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tutti"):
        evaluate(tmp_path, qrels)


def test_pool_rejects_changed_index(tmp_path):
    save(tmp_path / "manifest.json", {"indices": {a: {"uuid": "old"} for a in INDICES}})
    es = SimpleNamespace(indices=SimpleNamespace(get=lambda index: {index: {"settings": {"index": {"uuid": "new"}}}}))
    with pytest.raises(ValueError, match="ricreato"):
        pool(es, [{"id": "q1", "query": "Roma"}], tmp_path)


def test_prepare_only_recreates_dedicated_indices_and_preserves_mapping(monkeypatch, tmp_path):
    calls = []
    dump = tmp_path / "dump"
    dump.write_bytes(b"corpus immutato")
    def index_dump(path, es, name, *, stats, mappings):
        calls.append((path, name, mappings))
        stats.indexed_documents = 3
        stats.valid_articles = 3
    monkeypatch.setattr("wikinews_search.evaluation.index_dump", index_dump)
    es = SimpleNamespace(info=lambda: {"version": {"number": "8.15.0"}},
        indices=SimpleNamespace(flush=lambda **kw: None,
            stats=lambda **kw: {"_all": {"primaries": {"store": {"size_in_bytes": 100}}}},
            get=lambda index: {index: {"settings": {"index": {"uuid": index}}}}))
    prepare(es, dump, tmp_path)
    assert [c[1] for c in calls] == list(INDICES.values())
    assert calls[0][2]["properties"]["title"]["analyzer"] == "standard"
    assert calls[1][2]["properties"]["title"]["analyzer"] == "italiano"
    assert MAPPINGS["properties"]["title"]["analyzer"] == "italiano"
    assert len(json.loads((tmp_path / "manifest.json").read_text())["indices"]) == 2
