"""Trasformazione dei record del dump in articoli pronti per l'indicizzazione."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup

# Elementi HTML che non fanno parte del testo della notizia.
REMOVE_SELECTORS = [
    "head", "script", "style", "link", "meta", "sup", "table", "figure",
    "span.mw-editsection", ".noprint", ".reflist", ".references",
    "[typeof~='mw:Extension/references']",
]
BLOCK_TAGS = ["p", "li", "div", "section", "br", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]
# Categorie di servizio (minuscole) che non aiutano la navigazione.
IGNORED_CATEGORIES = {"pubblicati", "archiviati", "ricerche originali", "box wikivoyage probabilmente da rimuovere"}
# Prefissi (minuscoli) delle categorie di manutenzione: "Articoli da controllare per l'archiviazione",
# "Articoli archiviati", "Articoli con box interwiki verso Wikipedia", "Notizie per Wikivoyage scadute"...
IGNORED_PREFIXES = ("articol", "notizie per wikivoyage", "box wikivoyage")
# Categorie che sono solo una data ("3 aprile 2008"): non servono come filtro.
DATE_CATEGORY = re.compile(r"^\d{1,2} [^\W\d_]+ \d{4}$")
MIN_TEXT_CHARS = 40  # scarta redirect e pagine vuote


@dataclass
class Article:
    id: str
    title: str
    url: str
    body: str
    categories: list[str] = field(default_factory=list)
    date: datetime | None = None


def html_to_text(html: str) -> str:
    """Estrae il testo da HTML, un paragrafo per riga."""
    soup = BeautifulSoup(html, "lxml")
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


def record_to_article(record: dict) -> Article | None:
    """Converte un record del dump in Article; None se non e' una notizia indicizzabile."""
    namespace = record.get("namespace")
    if isinstance(namespace, dict) and namespace.get("identifier", 0) != 0:
        return None
    title = (record.get("name") or "").strip()
    identifier = record.get("identifier")
    html = (record.get("article_body") or {}).get("html") or ""
    if not title or identifier is None or not html:
        return None
    body = html_to_text(html)
    if len(body) < MIN_TEXT_CHARS:
        return None
    return Article(
        id=str(identifier),
        title=title,
        url=str(record.get("url") or ""),
        body=body,
        categories=clean_categories(record.get("categories")),
        date=parse_date(record.get("date_created")) or parse_date(record.get("date_modified")),
    )
