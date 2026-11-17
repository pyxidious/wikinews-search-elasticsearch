"""Interrogazione di Elasticsearch: costruzione della query, parsing della risposta."""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from markupsafe import escape

from .config import DEFAULT_INDEX, MAX_PAGE_SIZE, MAX_WINDOW, PAGE_SIZE
from .parsing import parse_date

SORTS = ("relevance", "date")
FIELDS = ["title^3", "body"]  # il titolo pesa 3 volte il testo


@dataclass
class Hit:
    id: str
    title: str
    url: str
    date: datetime | None
    categories: list[str]
    snippet: str  # HTML sicuro: testo con escape (encoder html) + tag <mark>
    score: float | None


@dataclass
class SearchResult:
    query: str
    total: int
    page: int
    page_count: int
    page_size: int
    hits: list[Hit]
    categories: list[tuple[str, int]] = field(default_factory=list)
    years: list[tuple[str, int]] = field(default_factory=list)
    elapsed_ms: float = 0.0


def normalize_query(query_string: str) -> str:
    # "Emilia-Romagna" non deve diventare "Emilia NOT Romagna": il trattino tra
    # due lettere e' parte della parola; l'esclusione vale solo a inizio termine.
    parts = re.split(r'("(?:\\.|[^"\\])*"|\\.)', query_string)
    return "".join(part if part.startswith(('"', '\\')) else
                   re.sub(r"(?<=\w)-(?=\w)", " ", part) for part in parts)


def split_negations(query_string: str) -> tuple[str, list[str]]:
    # Solo esclusioni autonome al livello esterno. Virgolette, escape e gruppi
    # restano al parser Lucene: una regex globale corrompeva '"Roma -Milano"'.
    positive, negatives = [], []
    i, depth, quoted = 0, 0, False
    while i < len(query_string):
        char = query_string[i]
        if char == "\\" and i + 1 < len(query_string):
            positive.append(query_string[i:i + 2])
            i += 2
            continue
        if char == '"':
            quoted = not quoted
        if not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            if char == "-" and depth == 0 and (i == 0 or query_string[i - 1].isspace()):
                match = re.match(r'-("(?:\\.|[^"\\])+"(?:~\d+)?|[^\s"()|+]+)', query_string[i:])
                if match:
                    negatives.append(match.group(1))
                    positive.append(" ")
                    i += len(match.group())
                    continue
        positive.append(char)
        i += 1
    return "".join(positive).strip(), negatives


def build_body(query_string: str, page: int, page_size: int, category: str | None = None,
               year: str | int | None = None, sort: str = "relevance") -> dict:
    """Parametri di es.search() (nomi del client Python: from_, source, ...)."""
    filters = []
    if category:
        filters.append({"term": {"category": category}})
    if year:
        filters.append({"term": {"year": str(year)}})
    positive, negatives = split_negations(query_string)
    text = normalize_query(positive).strip()
    if text:
        # simple_query_string non genera mai errori di sintassi: supporta
        # "frase", a + b (AND), a | b (OR), prefisso*, (gruppi), parola~1
        must = [{"simple_query_string": {"query": text, "fields": FIELDS,
                                         "default_operator": "or", "lenient": True}}]
    else:
        must = [{"match_all": {}}]
    must_not = [{"simple_query_string": {"query": normalize_query(n), "fields": FIELDS,
                                         "default_operator": "and", "lenient": True}} for n in negatives]
    body = {
        "query": {"bool": {"must": must, "filter": filters, **({"must_not": must_not} if must_not else {})}},
        "from_": (page - 1) * page_size,
        "size": page_size,
        "track_total_hits": True,
        "source": ["title", "url", "date", "category", "lead"],
        "highlight": {
            "pre_tags": ["<mark>"], "post_tags": ["</mark>"],
            "encoder": "html",  # escape dell'HTML presente nel testo
            "fields": {"body": {"fragment_size": 240, "number_of_fragments": 2}},
        },
        "aggs": {
            "categories": {"terms": {"field": "category", "size": 12}},
            "years": {"terms": {"field": "year", "size": 50, "order": {"_key": "desc"}}},
        },
    }
    if sort == "date":
        body["sort"] = [{"date": {"order": "desc", "missing": "_last"}}, "_score", {"article_id": "asc"}]
    else:
        body["sort"] = ["_score", {"article_id": "asc"}]
    return body


def parse_response(response: dict, query_string: str, page: int, page_size: int) -> SearchResult:
    total = response["hits"]["total"]["value"]
    hits = []
    for raw in response["hits"]["hits"]:
        source = raw["_source"]
        fragments = raw.get("highlight", {}).get("body")
        if fragments:
            snippet = " … ".join(fragments)
        else:
            lead = source.get("lead", "")
            snippet = str(escape(lead)) + ("…" if len(lead) >= 240 else "")
        hits.append(Hit(
            id=raw["_id"], title=source["title"], url=source.get("url", ""),
            date=parse_date(source.get("date")), categories=list(source.get("category") or []),
            snippet=snippet, score=raw.get("_score"),
        ))
    aggs = response.get("aggregations", {})
    return SearchResult(
        query=query_string, total=total, page=page, page_size=page_size,
        page_count=min(math.ceil(total / page_size), MAX_WINDOW // page_size) if total else 0, hits=hits,
        categories=[(b["key"], b["doc_count"]) for b in aggs.get("categories", {}).get("buckets", [])],
        years=[(b["key"], b["doc_count"]) for b in aggs.get("years", {}).get("buckets", [])],
    )


def search(es, query_string: str = "", page: int = 1, page_size: int = PAGE_SIZE,
           category: str | None = None, year: str | int | None = None, sort: str = "relevance",
           index: str = DEFAULT_INDEX) -> SearchResult:
    started = time.perf_counter()
    page_size = min(max(1, int(page_size)), MAX_PAGE_SIZE)
    page = min(max(1, int(page)), max(1, MAX_WINDOW // page_size))
    if not query_string.strip() and not category and not year:
        return SearchResult(query_string, 0, 1, 0, page_size, [])

    response = es.search(index=index, **build_body(query_string, page, page_size, category, year, sort))
    result = parse_response(response, query_string, page, page_size)
    if not result.hits and result.total and page > 1:  # pagina oltre la fine: ultima pagina
        page = result.page_count
        response = es.search(index=index, **build_body(query_string, page, page_size, category, year, sort))
        result = parse_response(response, query_string, page, page_size)
    result.elapsed_ms = (time.perf_counter() - started) * 1000
    return result


def get_article(es, article_id: str, index: str = DEFAULT_INDEX) -> dict | None:
    response = es.search(
        index=index, query={"ids": {"values": [str(article_id)]}}, size=1,
        source=["title", "url", "date", "category", "body"],
    )
    hits = response["hits"]["hits"]
    if not hits:
        return None
    source = hits[0]["_source"]
    return {
        "id": hits[0]["_id"], "title": source["title"], "url": source.get("url", ""),
        "body": source["body"], "date": parse_date(source.get("date")),
        "categories": list(source.get("category") or []),
    }


def count_documents(es, index: str = DEFAULT_INDEX) -> int:
    return es.count(index=index)["count"]
