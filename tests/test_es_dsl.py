"""Test unitari (senza server): costruzione della query, parsing della risposta, mapping."""
import pytest

from wikinews_search.indexer import MAPPINGS, SETTINGS, article_to_source
from wikinews_search.parsing import record_to_article
from wikinews_search.searcher import build_body, normalize_query, parse_response, search

from .fakes import RESPONSE, FakeES
from .sample_data import RECORDS


def test_text_query_uses_configuration_b_with_uniform_weights():
    body = build_body("terremoto", 1, 10)
    sqs = body["query"]["bool"]["must"][0]["simple_query_string"]
    assert sqs["query"] == "terremoto"
    assert sqs["fields"] == ["title", "body"]
    assert sqs["lenient"] is True
    assert body["query"]["bool"]["filter"] == []


def test_filters_are_term_queries():
    body = build_body("x", 1, 10, category="Italia", year=2023)
    assert body["query"]["bool"]["filter"] == [{"term": {"category": "Italia"}}, {"term": {"year": "2023"}}]


def test_filters_only_use_match_all():
    body = build_body("", 1, 10, category="Italia")
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


def test_sort_by_date_and_default_relevance():
    assert build_body("x", 1, 10)["sort"] == ["_score", {"article_id": "asc"}]
    assert build_body("x", 1, 10, sort="date")["sort"][0] == {"date": {"order": "desc", "missing": "_last"}}


def test_pagination_offsets():
    body = build_body("x", 3, 10)
    assert (body["from_"], body["size"]) == (20, 10)


def test_highlight_escapes_html_and_aggs_present():
    body = build_body("x", 1, 10)
    assert body["highlight"]["encoder"] == "html"
    assert set(body["aggs"]) == {"categories", "years"}


def test_hyphenated_words_are_not_negations():
    assert normalize_query("Emilia-Romagna") == "Emilia Romagna"
    assert normalize_query("elezioni -Roma") == "elezioni -Roma"


def test_negated_terms_become_must_not():
    query = build_body("elezioni -Roma", 1, 10)["query"]["bool"]
    assert query["must"][0]["simple_query_string"]["query"] == "elezioni"
    assert query["must_not"][0]["simple_query_string"]["query"] == "Roma"


def test_negated_phrase_and_negation_only():
    query = build_body('-"banca centrale"', 1, 10)["query"]["bool"]
    assert query["must"] == [{"match_all": {}}]
    assert query["must_not"][0]["simple_query_string"]["query"] == '"banca centrale"'


def test_hyphen_inside_word_is_not_a_negation_in_body():
    query = build_body("Emilia-Romagna", 1, 10)["query"]["bool"]
    assert "must_not" not in query and query["must"][0]["simple_query_string"]["query"] == "Emilia Romagna"


def test_search_caps_page_size_and_window():
    es = FakeES()
    search(es, "x", page=10**6, page_size=1000)
    call = es.calls[0]
    assert call["size"] == 50 and call["from_"] + call["size"] <= 10_000


def test_search_without_query_or_filters_does_not_call_es():
    es = FakeES()
    assert search(es, "   ").total == 0 and es.calls == []


def test_page_beyond_the_end_falls_back_to_last_page():
    es = FakeES()
    result = search(es, "terremoto", page=30, page_size=10)  # from_=290: pagina vuota, 25 risultati in totale
    assert result.page == 3 and len(es.calls) == 2 and result.hits


def test_parse_response():
    result = parse_response(RESPONSE, "terremoto", 1, 10)
    assert (result.total, result.page_count) == (25, 3)
    hit = result.hits[0]
    assert hit.id == "1002" and hit.date.year == 2023 and "<mark>terremoto</mark>" in hit.snippet
    assert result.categories[0] == ("Disastri e incidenti", 2) and result.years == [("2023", 1)]


def test_parse_response_fallback_snippet_is_escaped():
    response = {"hits": {"total": {"value": 1}, "hits": [
        {"_id": "1", "_score": 1.0, "_source": {"title": "T", "lead": "<script>x</script>"}}]}}
    snippet = parse_response(response, "q", 1, 10).hits[0].snippet
    assert "<script>" not in snippet and "&lt;script&gt;" in snippet


def test_article_to_source():
    source = article_to_source(record_to_article(RECORDS[0]))
    assert source["category"] == ["Politica", "Italia", "Roma"]
    assert source["year"] == "2024" and source["date"].startswith("2024-06-10")
    assert len(source["lead"]) <= 240


def test_index_definition():
    analyzer = SETTINGS["analysis"]["analyzer"]["italiano"]
    assert analyzer["filter"] == ["italian_elision", "lowercase", "italian_stop", "asciifolding", "italian_light_stemmer"]
    assert MAPPINGS["properties"]["title"]["analyzer"] == MAPPINGS["properties"]["body"]["analyzer"] == "italiano"
    assert MAPPINGS["properties"]["category"]["type"] == "keyword"
    assert SETTINGS["number_of_shards"] == 1
