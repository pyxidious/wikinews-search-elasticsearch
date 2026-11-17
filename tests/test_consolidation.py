"""Regressioni dei problemi verificati durante il consolidamento."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from wikinews_search.cli import main
from wikinews_search.dump import iter_records
from wikinews_search.indexer import build_index, iter_articles
from wikinews_search.parsing import html_to_text, record_to_article
from wikinews_search.searcher import build_body, normalize_query, parse_response, search, split_negations
from wikinews_search.statistics import IndexStats
from .fakes import RESPONSE
from .sample_data import RECORDS


@pytest.mark.parametrize("change,reason", [
    ({"namespace": 1}, "namespace"),
    ({"namespace": {"identifier": "1"}}, "namespace"),
    ({"name": 42}, "invalid_fields"),
    ({"article_body": []}, "invalid_fields"),
    ({"article_body": {"html": []}}, "missing_html"),
    ({"identifier": {}}, "missing_identity"),
    ({"categories": 12}, None),
])
def test_malformed_fields_are_classified(change, reason):
    stats = IndexStats()
    result = record_to_article({**RECORDS[0], **change}, stats)
    assert stats.discarded == ({reason: 1} if reason else {})
    assert bool(result) == (reason is None)


def test_redirects_are_incoming_and_namespace_string_zero_is_valid():
    assert record_to_article({**RECORDS[0], "namespace": {"identifier": "0"},
                              "redirects": [{"name": "Titolo alternativo"}]})


def test_real_dump_softredirect_lua_44564():
    # Struttura ridotta del record reale 44564, Lua: prima era solo short_text.
    record = {**RECORDS[0], "article_body": {"html": '<p><span id="softredirect" class="redirectText">w:Lua</span>'
              '<br/>Questa pagina è un Soft redirect.</p>'}}
    stats = IndexStats()
    assert record_to_article(record, stats) is None
    assert stats.discarded == {"redirect": 1}


def test_long_softredirect_is_also_classified_by_markup():
    # Variante sintetica: la classificazione non dipende dalla lunghezza.
    html = '<span id="softredirect">Questa pagina rimanda a un altro progetto Wikimedia.</span>'
    stats = IndexStats()
    assert record_to_article({**RECORDS[0], "article_body": {"html": html}}, stats) is None
    assert stats.discarded == {"redirect": 1}


def test_real_dump_quote_table_49166_and_caption_48882():
    # Frammenti minimi derivati dai due record; le tabelle di servizio restano escluse.
    html = ('<table class="metadata"><tr><td>Avviso di servizio</td></tr></table>'
            '<table><tr><td><div>Una folla si è arrampicata sulla statua del re coloniale Leopoldo II a Bruxelles.</div>'
            '</td></tr></table><figure><img src="foto.jpg"><figcaption>'
            "L'Hôpital Saint-Pierre di Bruxelles</figcaption></figure>")
    text = html_to_text(html)
    assert "Avviso di servizio" not in text
    assert "Leopoldo II" in text and "Saint-Pierre" in text


def test_stream_counts_invalid_json_and_non_objects(tmp_path):
    path = tmp_path / "bad.ndjson"
    path.write_bytes(b'null\n[]\n42\n{bad\n\xff\n\n')
    stats = IndexStats()
    assert list(iter_records(path, stats)) == []
    assert stats.records_read == 5
    assert stats.discarded == {"invalid_record": 3, "invalid_json": 2}


def test_validation_accounts_for_every_record(sample_dump, tmp_path, capsys):
    stats = IndexStats()
    assert len(list(iter_articles(sample_dump, stats))) == 11
    assert stats.records_read == stats.valid_articles + sum(stats.discarded.values()) == 14
    main(["validate-dump", "--dump", str(sample_dump), "--report", str(tmp_path / "stats.json")])
    assert '"records_read": 14' in capsys.readouterr().out


def test_bulk_counts_success_failures_and_unique_documents(monkeypatch):
    article = record_to_article(RECORDS[0])
    def bulk(es, actions, **kwargs):
        docs = list(actions)
        assert len(docs) == 3 and docs[0]["_id"] == docs[1]["_id"]
        yield True, {}
        yield True, {}
        yield False, {"index": {"status": 400}}
    monkeypatch.setattr("wikinews_search.indexer.helpers.streaming_bulk", bulk)
    es = SimpleNamespace(indices=SimpleNamespace(exists=lambda **kw: False, create=lambda **kw: None,
                                                 refresh=lambda **kw: None),
                         options=lambda **kw: None, count=lambda **kw: {"count": 1})
    stats = IndexStats()
    assert build_index(es, [article] * 3, "test", stats=stats) == 2
    assert (stats.indexed_operations, stats.indexed_documents, stats.indexing_errors) == (2, 1, 1)


@pytest.mark.parametrize("query", ['"Roma -Milano"', '"Emilia-Romagna"', r'"Roma \" -Milano"',
                                   '(Roma | -Milano)', r'Roma \-Milano'])
def test_phrases_groups_and_escapes_are_not_rewritten_as_global_negations(query):
    assert split_negations(query) == (query, [])


def test_hyphenated_phrase_remains_a_phrase():
    assert normalize_query('"Emilia-Romagna"') == '"Emilia-Romagna"'
    body = build_body('"Roma -Milano" -Torino', 1, 10)["query"]["bool"]
    assert body["must"][0]["simple_query_string"]["query"] == '"Roma -Milano"'
    assert body["must_not"][0]["simple_query_string"]["query"] == "Torino"


@pytest.mark.parametrize("size", [3, 7, 10, 49, 50])
def test_page_count_and_fallback_stay_in_window(size):
    response = deepcopy(RESPONSE)
    response["hits"]["total"]["value"] = 25001
    result = parse_response(response, "x", 1, size)
    assert result.page_count == 10000 // size
    calls = []
    def do_search(**kwargs):
        calls.append(kwargs)
        assert kwargs["from_"] + kwargs["size"] <= 10000
        return response
    es = SimpleNamespace(search=do_search)
    assert search(es, "x", page=100000, page_size=size).page == result.page_count
