"""Lettura in streaming del dump Wikimedia Enterprise (NDJSON, anche dentro tar.gz)."""
from __future__ import annotations

import gzip
import json
import logging
import tarfile
from pathlib import Path
from typing import BinaryIO, Iterator
from .statistics import IndexStats

log = logging.getLogger(__name__)


def _json_lines(stream: BinaryIO, stats: IndexStats | None = None) -> Iterator[dict]:
    # Si leggono righe in byte: i flussi tar in streaming non sono "seekable",
    # quindi non si puo' usare io.TextIOWrapper.
    for lineno, raw in enumerate(stream, start=1):
        raw = raw.strip()
        if not raw:
            continue
        if stats is not None:
            stats.records_read += 1
        try:
            record = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if stats is not None:
                stats.discarded["invalid_json"] += 1
            log.warning("Riga %d non valida, saltata", lineno)
            continue
        if not isinstance(record, dict):
            if stats is not None:
                stats.discarded["invalid_record"] += 1
            continue
        yield record


def iter_records(path: str | Path, stats: IndexStats | None = None) -> Iterator[dict]:
    """Restituisce i record JSON del dump senza caricarlo tutto in memoria.

    Formati supportati: .tar.gz / .tgz / .tar (ogni file e' NDJSON),
    .ndjson.gz / .json.gz e .ndjson / .json non compressi.
    """
    path = Path(path)
    name = path.name.lower()
    if name.endswith((".tar.gz", ".tgz", ".tar")):
        mode = "r|" if name.endswith(".tar") else "r|gz"
        with tarfile.open(path, mode) as tar:
            for member in tar:
                if not member.isfile():
                    continue
                stream = tar.extractfile(member)
                if stream is not None:
                    with stream:
                        yield from _json_lines(stream, stats)
    elif name.endswith(".gz"):
        with gzip.open(path, "rb") as stream:
            yield from _json_lines(stream, stats)
    else:
        with open(path, "rb") as stream:
            yield from _json_lines(stream, stats)
