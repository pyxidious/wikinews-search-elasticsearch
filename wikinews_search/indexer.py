"""Creazione dell'indice Elasticsearch (analizzatore italiano) e caricamento bulk."""
from __future__ import annotations

import logging
import os
import time
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator

from elasticsearch import Elasticsearch, helpers

from .config import DEFAULT_ES_URL, DEFAULT_INDEX
from .dump import iter_records
from .parsing import Article, record_to_article
from .statistics import IndexStats

log = logging.getLogger(__name__)

ELISIONS = ["c", "l", "all", "dall", "dell", "nell", "sull", "coll", "pell", "gl", "agl",
            "dagl", "degl", "negl", "sugl", "un", "m", "t", "s", "v", "d"]

SETTINGS = {
    "number_of_shards": 1,      # un solo shard: statistiche BM25 coerenti e risultati deterministici
    "number_of_replicas": 0,
    "analysis": {
        "filter": {
            "italian_elision": {"type": "elision", "articles_case": True, "articles": ELISIONS},
            "italian_stop": {"type": "stop", "stopwords": "_italian_"},
            "italian_light_stemmer": {"type": "stemmer", "language": "light_italian"},
        },
        "analyzer": {
            "italiano": {
                "tokenizer": "standard",
                # l'elisione toglie "l'" / "dell'"; asciifolding prima dello stemmer: citta == città
                "filter": ["italian_elision", "lowercase", "italian_stop",
                           "asciifolding", "italian_light_stemmer"],
            }
        },
    },
}

MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        "title": {"type": "text", "analyzer": "italiano"},
        "body": {"type": "text", "analyzer": "italiano"},
        "lead": {"type": "text", "index": False},      # primi caratteri, per lo snippet di riserva
        "url": {"type": "keyword", "index": False, "doc_values": False},
        "category": {"type": "keyword"},               # array di categorie
        "date": {"type": "date"},
        "year": {"type": "keyword"},
        "article_id": {"type": "keyword"},  # spareggio stabile; _id non e' ordinabile
    },
}


def make_client(url: str | None = None) -> Elasticsearch:
    """Client con URL da argomento/ES_URL; credenziali opzionali da ES_USERNAME / ES_PASSWORD."""
    kwargs = {}
    if os.environ.get("ES_USERNAME"):
        kwargs["basic_auth"] = (os.environ["ES_USERNAME"], os.environ.get("ES_PASSWORD", ""))
    return Elasticsearch(url or DEFAULT_ES_URL, request_timeout=60, **kwargs)


def iter_articles(dump_path: str | Path, stats: IndexStats | None = None) -> Iterator[Article]:
    for record in iter_records(dump_path, stats):
        article = record_to_article(record, stats)
        if article is not None:
            yield article


def article_to_source(article: Article) -> dict:
    source = {
        "article_id": article.id,
        "title": article.title,
        "body": article.body,
        "lead": article.body[:240],
        "url": article.url,
        "category": article.categories,
    }
    if article.date:
        source["date"] = article.date.isoformat()
        source["year"] = str(article.date.year)
    return source


def create_index(es: Elasticsearch, index_name: str, *, mappings=None) -> None:
    """Ricrea l'indice da zero."""
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    es.indices.create(index=index_name, settings=SETTINGS, mappings=mappings or MAPPINGS)


def build_index(es: Elasticsearch, articles: Iterable[Article], index_name: str = DEFAULT_INDEX,
                chunk_size: int = 500, *, stats: IndexStats | None = None, mappings=None) -> int:
    create_index(es, index_name, mappings=mappings)
    counter = 0

    def actions():
        nonlocal counter
        for article in articles:
            counter += 1
            if counter % 1000 == 0:
                log.info("%d articoli letti...", counter)
            yield {"_index": index_name, "_id": article.id, "_source": article_to_source(article)}

    success = 0
    for ok, item in helpers.streaming_bulk(es.options(request_timeout=120), actions(),
                                           chunk_size=chunk_size, raise_on_error=False):
        if ok:
            success += 1
            if stats is not None:
                stats.indexed_operations += 1
        else:
            if stats is not None:
                stats.indexing_errors += 1
            log.error("Errore bulk: %s", item)
    es.indices.refresh(index=index_name)
    if stats is not None:
        stats.indexed_documents = es.count(index=index_name)["count"]
    return success


def index_dump(dump_path, es: Elasticsearch | None = None, index_name: str = DEFAULT_INDEX,
               limit: int | None = None, *, stats: IndexStats | None = None, mappings=None) -> int:
    if limit is not None and limit <= 0:
        raise ValueError("limit deve essere positivo")
    started = time.perf_counter()
    es = es or make_client()
    articles = iter_articles(dump_path, stats)
    if limit:
        articles = islice(articles, limit)
    try:
        return build_index(es, articles, index_name, stats=stats, mappings=mappings)
    finally:
        if stats is not None:
            stats.elapsed_seconds = time.perf_counter() - started
