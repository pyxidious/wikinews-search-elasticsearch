"""Interfaccia web (Flask) e API JSON, basate su Elasticsearch."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, render_template, request, url_for
from elasticsearch import ApiError
from elastic_transport import TransportError

from .config import DEFAULT_ES_URL, DEFAULT_INDEX, MAX_PAGE_SIZE, PAGE_SIZE
from .searcher import SORTS, count_documents, get_article, search

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _parse_args():
    q = (request.args.get("q") or "").strip()[:300]
    category = (request.args.get("category") or "").strip()[:100] or None
    year = request.args.get("year") or ""
    year = year if re.fullmatch(r"\d{4}", year) else None
    sort = request.args.get("sort", "relevance")
    sort = sort if sort in SORTS else "relevance"
    page = request.args.get("page", 1, type=int) or 1
    return q, category, year, sort, max(1, page)


def create_app(client=None, index_name: str | None = None, es_url: str | None = None) -> Flask:
    index_name = index_name or DEFAULT_INDEX
    if client is None:
        from .indexer import make_client
        client = make_client(es_url)
    es = client
    if not es.ping():
        raise ConnectionError(
            f"Elasticsearch non raggiungibile su {es_url or DEFAULT_ES_URL}. "
            "Avviarlo con: docker compose up -d"
        )
    if not es.indices.exists(index=index_name):
        raise LookupError(f"Indice '{index_name}' non trovato. Eseguire prima: python -m wikinews_search index")

    app = Flask(__name__)

    def search_params(q, category, year, sort, page=1):
        return {k: v for k, v in dict(q=q, category=category, year=year,
                sort=sort if sort != "relevance" else None, page=page if page > 1 else None).items()
                if v not in (None, "")}

    @app.template_filter("external_url")
    def external_url(value):
        # L'escape HTML da solo non blocca URL javascript: nei dati indicizzati.
        if not isinstance(value, str) or any(ord(char) < 32 for char in value):
            return ""
        try:
            url = urlsplit(value)
            return value if url.scheme.lower() in {"http", "https"} and url.hostname else ""
        except ValueError:
            return ""

    @app.template_filter("data_it")
    def data_it(value):
        return f"{value.day} {MESI[value.month - 1]} {value.year}" if value else ""

    @app.route("/")
    def home():
        q, category, year, sort, page = _parse_args()
        searching = bool(q or category or year)
        result = search(es, q, page, PAGE_SIZE, category, year, sort, index_name) if searching else None

        def link(**overrides):
            params = {"q": q, "category": category, "year": year, "sort": sort if sort != "relevance" else None}
            params.update(overrides)
            return url_for("home", **{k: v for k, v in params.items() if v not in (None, "")})

        return render_template(
            "search.html", q=q, category=category, year=year, sort=sort, result=result,
            searching=searching, link=link,
            doc_count=count_documents(es, index_name),
        )

    @app.route("/article/<article_id>")
    def article(article_id):
        q, category, year, sort, page = _parse_args()
        doc = get_article(es, article_id, index_name, query_string=q)
        if doc is None:
            abort(404)
        return render_template("article.html", doc=doc, paragraphs=doc["body_html"].split("\n"),
                               q=q, back_url=url_for("home", **search_params(q, category, year, sort, page)),
                               doc_count=count_documents(es, index_name))

    @app.route("/api/search")
    def api_search():
        q, category, year, sort, page = _parse_args()
        size = min(request.args.get("page_size", PAGE_SIZE, type=int) or PAGE_SIZE, MAX_PAGE_SIZE)
        r = search(es, q, page, size, category, year, sort, index_name)
        return jsonify(
            query=r.query, total=r.total, page=r.page, page_count=r.page_count,
            page_size=r.page_size, elapsed_ms=round(r.elapsed_ms, 2),
            hits=[{
                "id": h.id, "title": h.title, "url": h.url, "score": h.score,
                "date": h.date.isoformat() if h.date else None,
                "categories": h.categories, "snippet_html": h.snippet,
            } for h in r.hits],
            facets={"category": r.categories, "year": r.years},
        )

    @app.route("/health")
    def health():
        return jsonify(status="ok", documents=count_documents(es, index_name))

    @app.errorhandler(404)
    def not_found(_):
        return render_template("search.html", q="", category=None, year=None, sort="relevance",
                               result=None, searching=False, doc_count=count_documents(es, index_name),
                               link=lambda **kw: url_for("home"), not_found=True), 404

    def service_unavailable(error):
        app.logger.warning("Elasticsearch non disponibile: %s", type(error).__name__)
        if request.path == "/health" or request.path.startswith("/api/"):
            return jsonify(status="unavailable", error="Elasticsearch o indice non disponibile"), 503
        return render_template("unavailable.html"), 503

    app.register_error_handler(ApiError, service_unavailable)
    app.register_error_handler(TransportError, service_unavailable)

    return app
