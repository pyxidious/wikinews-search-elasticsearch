"""Confronto controllato A/B/C: prepare, pool, evaluate. Nessun giudizio automatico."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import time
from copy import deepcopy
from pathlib import Path

from .indexer import MAPPINGS, index_dump, make_client
from .searcher import build_body
from .statistics import IndexStats

# Nomi fissi, distinti dall'indice applicativo anche quando ES_INDEX cambia.
INDICES = {"standard": "itwikinews_hw4_standard", "italiano": "itwikinews_hw4_italiano"}
CONFIGS = {"A": ("standard", ["title", "body"]),
           "B": ("italiano", ["title", "body"]),
           "C": ("italiano", ["title^3", "body"])}
QUERY_PATH = Path(__file__).resolve().parent.parent / "experiments" / "queries.json"


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(es, dump, out):
    """Due indici bastano: B e C differiscono solo nei pesi della query."""
    manifest = {"dump": Path(dump).name, "sha256": checksum(dump),
                "python": platform.python_version(), "elasticsearch": dict(es.info()), "indices": {}}
    for analyzer, name in INDICES.items():
        mapping = deepcopy(MAPPINGS)
        for field in ("title", "body"):
            mapping["properties"][field]["analyzer"] = analyzer
        stats = IndexStats()
        index_dump(dump, es, name, stats=stats, mappings=mapping)
        if stats.indexing_errors:
            raise ValueError(f"Errori bulk in {name}: esperimento interrotto")
        # Flush rende la misura dello store piu' riproducibile; niente force merge.
        es.indices.flush(index=name)
        size = es.indices.stats(index=name, metric="store")["_all"]["primaries"]["store"]["size_in_bytes"]
        manifest["indices"][analyzer] = {"name": name, "uuid": es.indices.get(index=name)[name]["settings"]["index"]["uuid"],
                                          "stats": stats.to_dict(), "store_bytes": size}
    counts = [v["stats"]["indexed_documents"] for v in manifest["indices"].values()]
    if len(set(counts)) != 1:
        raise ValueError("Corpus diversi tra gli indici")
    save(out / "manifest.json", manifest)


def percentile(values, fraction):
    """Percentile nearest-rank, documentato e senza dipendenze aggiuntive."""
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def pool(es, queries, out, repeats=5):
    if repeats < 1 or not queries or len({q["id"] for q in queries}) != len(queries):
        raise ValueError("Query non vuote, ID unici e repeats >= 1 richiesti")
    manifest = read(out / "manifest.json")
    for analyzer, name in INDICES.items():
        actual = es.indices.get(index=name)[name]["settings"]["index"]["uuid"]
        if actual != manifest["indices"][analyzer]["uuid"]:
            raise ValueError("Indice ricreato dopo prepare: ripetere l'esperimento")
    runs = {"queries": queries, "manifest_sha256": checksum(out / "manifest.json"),
            "depth": 10, "repeats": repeats, "rankings": {}, "latency_ms": {c: [] for c in CONFIGS}}
    candidates = {}
    for q in queries:
        runs["rankings"][q["id"]] = {}
        # Warm-up escluso dalle misure, poi ordine ruotato per ridurre l'effetto cache.
        for iteration in range(repeats + 1):
            order = list(CONFIGS)
            shift = iteration % len(order)
            for config in order[shift:] + order[:shift]:
                analyzer, fields = CONFIGS[config]
                body = build_body(q["query"], 1, 10)
                bool_query = body["query"]["bool"]
                for clause in bool_query["must"] + bool_query.get("must_not", []):
                    if "simple_query_string" in clause:
                        clause["simple_query_string"]["fields"] = fields
                body["source"] = ["title", "url", "body"]
                # Stesso percorso delle query; il tempo include rete e deserializzazione.
                started = time.perf_counter()
                response = es.search(index=INDICES[analyzer], **body)
                elapsed = (time.perf_counter() - started) * 1000
                if iteration:
                    runs["latency_ms"][config].append(elapsed)
                if iteration == 0:
                    hits = response["hits"]["hits"]
                    runs["rankings"][q["id"]][config] = [h["_id"] for h in hits]
                    for hit in hits:
                        candidates[(q["id"], hit["_id"])] = hit["_source"]
    save(out / "runs.json", runs)
    # Ordine indipendente dalla configurazione e dal rango: valutazione cieca.
    keys = sorted(candidates, key=lambda key: hashlib.sha256(repr(key).encode()).hexdigest())
    with (out / "candidates.jsonl").open("w", encoding="utf-8") as stream:
        for qid, docid in keys:
            stream.write(json.dumps({"query_id": qid, "document_id": docid,
                                     **candidates[(qid, docid)]}, ensure_ascii=False) + "\n")
    # Non sovrascrivere giudizi umani di un esperimento precedente.
    with (out / "qrels-template.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["query_id", "document_id", "grade", "assessor", "note"])
        writer.writerows((qid, docid, "", "", "") for qid, docid in keys)


def metrics(ranking, judgments):
    relevant = {doc for doc, grade in judgments.items() if grade > 0}
    precision = sum(doc in relevant for doc in ranking[:5]) / 5
    rr = next((1 / rank for rank, doc in enumerate(ranking[:10], 1) if doc in relevant), 0.0)
    def dcg(grades):
        return sum((2 ** grade - 1) / math.log2(i + 2) for i, grade in enumerate(grades))
    ideal = dcg(sorted(judgments.values(), reverse=True)[:10])
    ndcg = dcg([judgments[doc] for doc in ranking[:10]]) / ideal if ideal else 0.0
    return {"P@5": precision, "MRR@10": rr, "nDCG@10": ndcg}


def evaluate(out, qrels):
    runs = read(out / "runs.json")
    if checksum(out / "manifest.json") != runs["manifest_sha256"]:
        raise ValueError("Manifest non corrispondente ai run")
    expected = {(qid, doc) for qid, configs in runs["rankings"].items()
                for ranking in configs.values() for doc in ranking}
    judgments = {q["id"]: {} for q in runs["queries"]}
    seen = set()
    with Path(qrels).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = row["query_id"], row["document_id"]
            if key in seen or key not in expected or row["grade"] not in {"0", "1", "2"} or not row["assessor"].strip():
                raise ValueError(f"Giudizio incompleto, duplicato o estraneo: {key}")
            seen.add(key)
            judgments[key[0]][key[1]] = int(row["grade"])
    if seen != expected:
        raise ValueError("Giudicare tutti i candidati del pool prima di calcolare le metriche")
    result = {"depth": 10, "qrels_sha256": checksum(qrels), "runs_sha256": checksum(out / "runs.json"),
              "queries_without_relevant": [qid for qid, j in judgments.items() if not any(j.values())],
              "configs": {}}
    for config in CONFIGS:
        per_query = {qid: metrics(configs[config], judgments[qid]) for qid, configs in runs["rankings"].items()}
        summary = {metric: sum(m[metric] for m in per_query.values()) / len(per_query)
                   for metric in ("P@5", "MRR@10", "nDCG@10")}
        times = runs["latency_ms"][config]
        result["configs"][config] = {"mean": summary, "per_query": per_query,
                                      "latency_p50_ms": percentile(times, .50),
                                      "latency_p95_ms": percentile(times, .95)}
    save(out / "metrics.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "pool", "evaluate"])
    parser.add_argument("--out", type=Path, required=True, help="cartella di questa esecuzione")
    parser.add_argument("--dump", type=Path)
    parser.add_argument("--queries", type=Path, default=QUERY_PATH)
    parser.add_argument("--qrels", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--es-url")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.command == "prepare":
        if not args.dump:
            parser.error("prepare richiede --dump")
        if (args.out / "manifest.json").exists():
            parser.error("usare una cartella nuova per ogni preparazione")
        prepare(make_client(args.es_url), args.dump, args.out)
    elif args.command == "pool":
        if (args.out / "runs.json").exists():
            parser.error("run gia' presente: usare una nuova esecuzione")
        pool(make_client(args.es_url), read(args.queries), args.out, args.repeats)
    else:
        if not args.qrels:
            parser.error("evaluate richiede --qrels")
        print(json.dumps(evaluate(args.out, args.qrels), indent=2))


if __name__ == "__main__":
    main()
