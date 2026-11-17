"""Trasformazione dei record del dump in articoli pronti per l'indicizzazione."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup
from .statistics import IndexStats

# Elementi HTML che non fanno parte del testo della notizia.
REMOVE_SELECTORS = [
    "head", "script", "style", "link", "meta", "sup",
    "table.metadata", "table.navbox", "table.infobox", "table.toc", "table.avviso",
    "span.mw-editsection", ".noprint", ".reflist", ".references",
    "[typeof~='mw:Extension/references']",
]
BLOCK_TAGS = ["p", "li", "div", "section", "br", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "td", "th", "figcaption"]
# Categorie di servizio (minuscole) che non aiutano la navigazione.
IGNORED_CATEGORIES = {"pubblicati", "archiviati", "ricerche originali", "box wikivoyage probabilmente da rimuovere"}
# Prefissi (minuscoli) delle categorie di manutenzione: "Articoli da controllare per l'archiviazione",
# "Articoli archiviati", "Articoli con box interwiki verso Wikipedia", "Notizie per Wikivoyage scadute"...
IGNORED_PREFIXES = ("articol", "notizie per wikivoyage", "box wikivoyage")
# Categorie che sono solo una data ("3 aprile 2008"): non servono come filtro.
DATE_CATEGORY = re.compile(r"^\d{1,2} [^\W\d_]+ \d{4}$")
MIN_TEXT_CHARS = 40  # euristica per pagine troppo brevi, non prova di redirect


@dataclass
class Article:
    id: str
    title: str
    url: str
    body: str
    categories: list[str] = field(default_factory=list)
    date: datetime | None = None


def html_to_text(html: str | BeautifulSoup) -> str:
    """Estrae il testo da HTML, un paragrafo per riga."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")
    for selector in REMOVE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()
    for tag in soup.find_all(BLOCK_TAGS):
        tag.append("\n")
    text = soup.get_text("")
    text = re.sub(r"[ \t\r\f\v\u00a0]+", " ", text)
    text = re.sub(r" ?\n[ \n]*", "\n", text)
    return text.strip()


def parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def clean_categories(raw) -> list[str]:
    result: list[str] = []
    if not isinstance(raw, list):
        return result
    for item in raw or []:
        name = item.get("name") if isinstance(item, dict) else item
        if not name:
            continue
        name = str(name)
        if ":" in name and name.split(":", 1)[0].strip().lower() in {"categoria", "category"}:
            name = name.split(":", 1)[1]
        name = re.sub(r"\s+", " ", name.replace("_", " ").replace(",", " ")).strip()
        lowered = name.lower()
        if (name and lowered not in IGNORED_CATEGORIES and not lowered.startswith(IGNORED_PREFIXES)
                and not DATE_CATEGORY.match(name) and name not in result):
            result.append(name)
    return result


def record_to_article(record: dict, stats: IndexStats | None = None) -> Article | None:
    """Converte un record del dump in Article; None se non e' una notizia indicizzabile."""
    def reject(reason):
        if stats is not None:
            stats.discarded[reason] += 1
        return None

    if not isinstance(record, dict):
        return reject("invalid_record")
    namespace = record.get("namespace")
    namespace = namespace.get("identifier") if isinstance(namespace, dict) else namespace
    if namespace not in (None, 0, "0"):
        return reject("namespace")
    # `redirects` elenca pagine che puntano a QUESTA pagina: non va scartata.
    title = record.get("name")
    identifier = record.get("identifier")
    article_body = record.get("article_body")
    if not isinstance(title, str) or not isinstance(article_body, dict):
        return reject("invalid_fields")
    title = title.strip()
    html = article_body.get("html")
    if not title or not isinstance(identifier, (str, int)) or isinstance(identifier, bool) or not str(identifier).strip():
        return reject("missing_identity")
    if not isinstance(html, str) or not html.strip():
        return reject("missing_html")
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one('#softredirect, link[rel~="mw:PageProp/redirect"]'):
        return reject("redirect")
    body = html_to_text(soup)
    if len(body) < MIN_TEXT_CHARS:
        return reject("short_text")
    if stats is not None:
        stats.valid_articles += 1
    return Article(
        id=str(identifier),
        title=title,
        url=str(record.get("url") or ""),
        body=body,
        categories=clean_categories(record.get("categories")),
        date=parse_date(record.get("date_created")) or parse_date(record.get("date_modified")),
    )
