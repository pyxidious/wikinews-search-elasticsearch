"""Smoke test end-to-end sul dump reale. Richiede Elasticsearch attivo e: WIKINEWS_DUMP=data/<file>.json.tar.gz"""
import os

import pytest

from wikinews_search.indexer import index_dump
from wikinews_search.searcher import search

DUMP = os.environ.get("WIKINEWS_DUMP")
pytestmark = [pytest.mark.realdump, pytest.mark.skipif(not DUMP, reason="WIKINEWS_DUMP non impostata")]


def test_real_dump_first_articles(es):
    name = "itwikinews_test_real"
    try:
        assert index_dump(DUMP, es, name, limit=2000) > 100, "troppo pochi articoli validi: controllare il parsing"
        result = search(es, "Italia", index=name)
        assert result.total > 0
        assert all(h.title and h.url.startswith("http") for h in result.hits)
    finally:
        es.indices.delete(index=name, ignore_unavailable=True)
