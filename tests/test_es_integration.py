"""Test di integrazione su Elasticsearch reale (saltati se il server non e' raggiungibile).

Avvio locale:  docker compose up -d      poi:  python -m pytest
"""
import json
from pathlib import Path

import pytest

from wikinews_search.indexer import index_dump
from wikinews_search.searcher import count_documents, get_article, search

pytestmark = pytest.mark.elasticsearch
GOLD = json.loads((Path(__file__).parent / "relevance_queries.json").read_text(encoding="utf-8"))


@pytest.fixture
def run(es, index_name):
    return lambda q="", **kw: search(es, q, index=index_name, **kw)


def ids(result):
    return [h.id for h in result.hits]


# --- indicizzazione ---------------------------------------------------------------------------
def test_only_valid_articles_are_indexed(es, index_name):
    assert count_documents(es, index_name) == 11  # 14 record - 3 scartati


def test_rebuild_is_idempotent(es, sample_dump):
    name = "itwikinews_test_rebuild"
    try:
        assert index_dump(sample_dump, es, name) == 11
        assert index_dump(sample_dump, es, name) == 11
        assert count_documents(es, name) == 11
    finally:
        es.indices.delete(index=name, ignore_unavailable=True)


def test_limit_option(es, sample_dump):
    name = "itwikinews_test_limit"
    try:
        assert index_dump(sample_dump, es, name, limit=4) == 4
    finally:
        es.indices.delete(index=name, ignore_unavailable=True)


def test_italian_analyzer_output(es, index_name):
    tokens = es.indices.analyze(index=index_name, analyzer="italiano", text="L'Italia è la città più bella")["tokens"]
    terms = [t["token"] for t in tokens]
    assert "l" not in terms and "la" not in terms          # elisione e stopword
    assert any(t.startswith("ital") for t in terms)
    assert all(t == t.lower() and t.isascii() for t in terms)  # minuscolo e senza accenti


# --- ricerca ----------------------------------------------------------------------------------
def test_stemming_matches_inflected_forms(run):
    assert {"1001", "1009"} <= set(ids(run("elezione")))


def test_elision_and_accents(run):
    assert "1003" in ids(run("Italia"))    # "L'Italia vince..."
    assert "1006" in ids(run("citta")) and "1006" in ids(run("città"))


def test_stopwords_alone_return_nothing(run):
    assert run("il di la per").total == 0


def test_title_match_is_ranked_above_body_mentions(run):
    assert ids(run("inflazione"))[0] == "1005"


def test_phrase_query(run):
    assert ids(run('"legge di bilancio"')) == ["1015"]


def test_negation(run):
    result = ids(run("elezioni -Roma"))
    assert "1001" not in result and "1009" in result


def test_hyphenated_words_are_not_negations(run):
    assert ids(run("Emilia-Romagna"))[0] == "1008"


def test_filter_by_category_and_year(run):
    assert set(ids(run("", category="Disastri e incidenti"))) == {"1002", "1008"}
    assert set(ids(run("", category="Italia", year=2023))) == {"1006", "1008"}


def test_sort_by_date_is_descending(run):
    dates = [h.date for h in run("", category="Italia", sort="date").hits]
    assert dates == sorted(dates, reverse=True)


def test_facets_counts(run):
    result = run("elezioni")
    assert dict(result.categories)["Politica"] == 2
    assert dict(result.years) == {"2024": 1, "2022": 1}


def test_pagination(run):
    p1 = run("", category="Italia", page=1, page_size=2)
    p2 = run("", category="Italia", page=2, page_size=2)
    assert p1.total == p2.total == 5 and p1.page_count == 3
    assert not set(ids(p1)) & set(ids(p2))


def test_page_out_of_range_is_clamped(run):
    assert run("elezioni", page=99).page == 1


def test_no_results_and_empty_query(run):
    assert run("xyzqwerty").total == 0 and run("").total == 0


@pytest.mark.parametrize("q", ['"', "((", "AND", "OR OR", "*", "title:", "a:b:c", "\\", "[1 TO", "~", "-", "+"])
def test_malformed_queries_do_not_crash(run, q):
    run(q)


def test_snippet_is_highlighted_and_escaped(run):
    hit = run("script alert").hits[0]
    assert hit.id == "1010" and "<script>" not in hit.snippet and "<mark>" in hit.snippet


def test_snippet_highlights_inflected_match(run):
    assert "<mark>" in run("elezione comunale").hits[0].snippet


def test_get_article(es, index_name):
    assert get_article(es, "1002", index_name)["title"].startswith("Terremoto")
    assert get_article(es, "999999", index_name) is None


# --- qualita' del ranking ---------------------------------------------------------------------
def test_gold_set_metrics(run):
    reciprocal_ranks, p_at_1, failures = [], 0, []
    for item in GOLD:
        got = ids(run(item["query"]))
        rank = got.index(item["expected"]) + 1 if item["expected"] in got else None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        p_at_1 += rank == 1
        if rank != 1:
            failures.append((item["query"], got[:3]))
    mrr = sum(reciprocal_ranks) / len(GOLD)
    assert p_at_1 / len(GOLD) >= 0.8, f"P@1 troppo bassa; errori: {failures}"
    assert mrr >= 0.9, f"MRR troppo bassa: {mrr:.2f}; errori: {failures}"


# --- sistema (web + Elasticsearch reale) ------------------------------------------------------
def test_web_end_to_end(client):
    html = client.get("/?q=elezioni").get_data(as_text=True)
    assert "Elezioni comunali a Roma" in html and "<mark>" in html and "Politica" in html
    assert client.get("/article/1002").status_code == 200
    assert client.get("/article/424242").status_code == 404
    assert client.get("/api/search?q=terremoto").get_json()["hits"][0]["id"] == "1002"
    assert client.get("/health").get_json()["status"] == "ok"


def test_web_escapes_stored_html(client):
    assert "<script>alert(1)" not in client.get("/?q=script+alert").get_data(as_text=True)
    assert "<script>alert(1)" not in client.get("/article/1010").get_data(as_text=True)


# --- prestazioni ------------------------------------------------------------------------------
def test_query_latency_on_small_index(run):
    import time
    times = []
    for q in ["terremoto", "elezioni Roma", "inflazione tassi", "calcio europei", "vaccino"] * 10:
        t = time.perf_counter()
        run(q)
        times.append(time.perf_counter() - t)
    times.sort()
    assert times[int(len(times) * 0.95)] < 0.25
