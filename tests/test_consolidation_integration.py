"""Verifiche su Lucene reale: semantica delle query e paginazione."""
import uuid

import pytest
from elasticsearch import helpers

from wikinews_search.indexer import create_index
from wikinews_search.searcher import search

pytestmark = pytest.mark.elasticsearch


def test_operators_against_lucene(es, index_name):
    def ids(query):
        return {h.id for h in search(es, query, index=index_name).hits}
    assert {"1001", "1009"} <= ids("Roma Macron")
    assert not ids("Roma + Macron")
    assert {"1001", "1009"} <= ids("Roma | Macron")
    assert ids('"Emilia-Romagna"') == {"1008"}
    assert ids('"legge di bilancio" -Roma') == {"1015"}
    assert ids("elezion*") == {"1001", "1009"}
    assert "1002" in ids("terremoto~1")
    # Il trattino dentro la frase non diventa un'esclusione globale.
    assert ids('"Emilia -Romagna"') == {"1008"}


def test_equal_scores_dates_and_window_boundary(es):
    name = "itwikinews_test_window_" + uuid.uuid4().hex[:8]
    try:
        create_index(es, name)
        helpers.bulk(es, ({"_index": name, "_id": str(i), "_source": {
            "article_id": f"{i:05d}", "title": "Notizia comune", "body": "Testo identico",
            "date": "2020-01-01", "category": ["Prova"]}} for i in range(10003)))
        es.indices.refresh(index=name)
        for sort in ("date", "relevance"):
            first = search(es, "notizia", page_size=7, sort=sort, index=name)
            second = search(es, "notizia", page=2, page_size=7, sort=sort, index=name)
            last = search(es, "notizia", page=10**6, page_size=7, sort=sort, index=name)
            assert [h.id for h in first.hits] == [str(i) for i in range(7)]
            assert [h.id for h in second.hits] == [str(i) for i in range(7, 14)]
            assert last.total == 10003 and last.page == last.page_count == 1428
            assert len(last.hits) == 7
    finally:
        es.indices.delete(index=name, ignore_unavailable=True)
