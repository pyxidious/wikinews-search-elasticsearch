"""Lettura in streaming del dump Wikimedia Enterprise (NDJSON, anche dentro tar.gz)."""
from __future__ import annotations

import gzip
import json
import logging
import tarfile
from pathlib import Path
from typing import BinaryIO, Iterator

log = logging.getLogger(__name__)


def _json_lines(stream: BinaryIO) -> Iterator[dict]:
    # Si leggono righe in byte: i flussi tar in streaming non sono "seekable",
    # quindi non si puo' usare io.TextIOWrapper.
    for lineno, raw in enumerate(stream, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("Riga %d non valida, saltata", lineno)


def iter_records(path: str | Path) -> Iterator[dict]:
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
                    yield from _json_lines(stream)
    elif name.endswith(".gz"):
        with gzip.open(path, "rb") as stream:
            yield from _json_lines(stream)
    else:
        with open(path, "rb") as stream:
            yield from _json_lines(stream)
