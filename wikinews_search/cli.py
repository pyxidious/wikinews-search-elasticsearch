"""Riga di comando: download, index, validate-dump, serve, stats."""
from __future__ import annotations

import argparse
import logging
import json
import time
import sys
import urllib.request
from pathlib import Path

from .config import DEFAULT_DUMP_PATH, DEFAULT_DUMP_URL, DEFAULT_ES_URL, DEFAULT_INDEX


def download(url: str, dest: Path, force: bool = False) -> Path:
    dest = Path(dest)
    if dest.exists() and not force:
        print(f"Dump gia' presente: {dest} (usare --force per riscaricarlo)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "wikinews-search-homework/1.0"})
    with urllib.request.urlopen(request) as response, open(part, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\rScaricati {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", file=sys.stderr)
    part.replace(dest)
    print(f"\nSalvato in {dest}")
    return dest


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="wikinews_search", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_es_options(p):
        p.add_argument("--es-url", default=DEFAULT_ES_URL, help="indirizzo di Elasticsearch (o variabile ES_URL)")
        p.add_argument("--index-name", default=DEFAULT_INDEX, help="nome dell'indice (o variabile ES_INDEX)")

    p = sub.add_parser("download", help="scarica il dump di it.wikinews")
    p.add_argument("--url", default=DEFAULT_DUMP_URL)
    p.add_argument("--dest", type=Path, default=DEFAULT_DUMP_PATH)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("index", help="crea l'indice Elasticsearch dal dump")
    p.add_argument("--dump", type=Path, default=DEFAULT_DUMP_PATH)
    p.add_argument("--limit", type=int, default=None, help="indicizza solo i primi N articoli (debug)")
    p.add_argument("--report", type=Path, help="salva statistiche JSON")
    add_es_options(p)

    p = sub.add_parser("validate-dump", help="valida tutto il dump in streaming senza Elasticsearch")
    p.add_argument("--dump", type=Path, default=DEFAULT_DUMP_PATH)
    p.add_argument("--report", type=Path)

    p = sub.add_parser("serve", help="avvia l'interfaccia web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    add_es_options(p)

    p = sub.add_parser("stats", help="mostra il numero di documenti indicizzati")
    add_es_options(p)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.command == "download":
        download(args.url, args.dest, args.force)
    elif args.command == "index":
        from .indexer import index_dump, make_client
        from .statistics import IndexStats
        stats = IndexStats()
        try:
            count = index_dump(args.dump, make_client(args.es_url), args.index_name, args.limit, stats=stats)
        finally:
            report = json.dumps(stats.to_dict(), ensure_ascii=False, indent=2)
            print(report)
            if args.report:
                args.report.write_text(report, encoding="utf-8")
        print(f"Indicizzati {count} articoli nell'indice '{args.index_name}'")
        if stats.indexing_errors:
            raise SystemExit(1)
    elif args.command == "validate-dump":
        from .indexer import iter_articles
        from .statistics import IndexStats
        stats = IndexStats()
        started = time.perf_counter()
        for _ in iter_articles(args.dump, stats):
            pass
        stats.elapsed_seconds = time.perf_counter() - started
        report = json.dumps(stats.to_dict(), ensure_ascii=False, indent=2)
        print(report)
        if args.report:
            args.report.write_text(report, encoding="utf-8")
    elif args.command == "serve":
        from .webapp import create_app
        create_app(index_name=args.index_name, es_url=args.es_url).run(host=args.host, port=args.port)
    elif args.command == "stats":
        from .indexer import make_client
        from .searcher import count_documents
        print(count_documents(make_client(args.es_url), args.index_name), "documenti indicizzati")
