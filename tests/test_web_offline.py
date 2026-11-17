"""Test dell'interfaccia web con client Elasticsearch finto (nessun server necessario)."""
import pytest

from wikinews_search.webapp import create_app

from .fakes import FakeES
from .fakes import ARTICLE, RESPONSE
from copy import deepcopy


def test_home_page(fake_client):
    r = fake_client.get("/")
    assert r.status_code == 200 and "11" in r.get_data(as_text=True)


def test_search_page_renders_hits_facets_highlight(fake_client):
    html = fake_client.get("/?q=terremoto").get_data(as_text=True)
    assert "Terremoto in Turchia" in html and "<mark>terremoto</mark>" in html
    assert "Categorie" in html and "Disastri e incidenti" in html and "6 febbraio 2023" in html
    assert "Pagina 1 di 3" in html


def test_filters_reach_elasticsearch(fake_es, fake_client):
    fake_client.get("/?q=terremoto&category=Turchia&year=2023&sort=date&page=2")
    call = fake_es.calls[-1]
    assert {"term": {"category": "Turchia"}} in call["query"]["bool"]["filter"]
    assert {"term": {"year": "2023"}} in call["query"]["bool"]["filter"]
    assert call["from_"] == 10 and "sort" in call


def test_no_results(fake_client):
    assert "Nessun risultato" in fake_client.get("/?q=xyzqwerty").get_data(as_text=True)


def test_query_is_escaped(fake_client):
    assert "<script>alert(1)</script>" not in fake_client.get("/?q=<script>alert(1)</script>").get_data(as_text=True)


@pytest.mark.parametrize("params", ["page=abc", "page=-3", "year=abcd&q=roma", "sort=hack&q=roma", "q=" + "a" * 5000])
def test_bad_parameters(fake_client, params):
    assert fake_client.get("/?" + params).status_code == 200


def test_article_and_404(fake_client):
    assert "Le squadre di soccorso" in fake_client.get("/article/1002").get_data(as_text=True)
    assert fake_client.get("/article/424242").status_code == 404
    assert fake_client.get("/non-esiste").status_code == 404


def test_api_contract(fake_client):
    data = fake_client.get("/api/search?q=terremoto").get_json()
    assert set(data) >= {"query", "total", "page", "page_count", "hits", "facets", "elapsed_ms"}
    assert set(data["hits"][0]) >= {"id", "title", "url", "date", "categories", "snippet_html", "score"}
    assert fake_client.get("/api/search?q=x&page_size=1000").get_json()["page_size"] == 50


def test_health(fake_client):
    assert fake_client.get("/health").get_json() == {"status": "ok", "documents": 11}


def test_clear_errors_when_elasticsearch_is_down_or_index_missing():
    with pytest.raises(ConnectionError, match="docker compose up"):
        create_app(client=FakeES(reachable=False))
    with pytest.raises(LookupError, match="python -m wikinews_search index"):
        create_app(client=FakeES(index_exists=False))


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,test", "https://[broken", "https://example.org/\npath"])
def test_article_source_does_not_allow_active_or_malformed_urls(fake_client, monkeypatch, url):
    monkeypatch.setitem(ARTICLE, "url", url)
    html = fake_client.get("/article/1002").get_data(as_text=True)
    assert "Leggi l'originale" not in html


def test_web_page_limit_is_visible_and_has_no_unreachable_next_link(fake_client, fake_es, monkeypatch):
    response = deepcopy(RESPONSE)
    response["hits"]["total"]["value"] = 25001
    monkeypatch.setattr(fake_es, "search", lambda **kw: response)
    html = fake_client.get("/?q=notizia&page=100000").get_data(as_text=True)
    assert "Pagina 1000 di 1000" in html and 'rel="next"' not in html
    assert "Sono navigabili solo le prime 10000" in html
