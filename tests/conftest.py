import io
import json
import os
import tarfile
import uuid

import pytest
from elasticsearch import Elasticsearch

from wikinews_search.indexer import index_dump
from wikinews_search.webapp import create_app

from .fakes import FakeES
from .sample_data import RECORDS

ES_URL = os.environ.get("ES_URL", "http://localhost:9200")


def write_ndjson(path, records):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


@pytest.fixture(scope="session")
def sample_dump(tmp_path_factory):
    """Dump di prova in formato tar.gz con NDJSON dentro, come quello reale."""
    folder = tmp_path_factory.mktemp("dump")
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS).encode("utf-8")
    path = folder / "itwikinews-sample.json.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo("itwikinews_namespace_0_chunk_0.ndjson")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return path


# ---- test offline (client finto) ------------------------------------------------------------
@pytest.fixture
def fake_es():
    return FakeES()


@pytest.fixture
def fake_client(fake_es):
    return create_app(client=fake_es, index_name="test").test_client()


# ---- test di integrazione (Elasticsearch reale; saltati se non raggiungibile) ----------------
@pytest.fixture(scope="session")
def es():
    client = Elasticsearch(ES_URL, request_timeout=30)
    try:
        reachable = client.ping()
    except Exception:
        reachable = False
    if not reachable:
        pytest.skip(f"Elasticsearch non raggiungibile su {ES_URL}")
    return client


@pytest.fixture(scope="session")
def index_name(es, sample_dump):
    name = f"itwikinews_test_{uuid.uuid4().hex[:8]}"
    index_dump(sample_dump, es, name)
    yield name
    es.indices.delete(index=name, ignore_unavailable=True)


@pytest.fixture
def client(es, index_name):
    return create_app(client=es, index_name=index_name).test_client()
