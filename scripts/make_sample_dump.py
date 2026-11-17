"""Crea un piccolo dump di prova (stesso formato di quello reale) per provare il sistema senza scaricare nulla.

Uso:  python scripts/make_sample_dump.py data/sample.json.tar.gz
"""
import io
import json
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.sample_data import RECORDS  # noqa: E402

dest = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample.json.tar.gz")
dest.parent.mkdir(parents=True, exist_ok=True)
payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS).encode("utf-8")
with tarfile.open(dest, "w:gz") as tar:
    info = tarfile.TarInfo("itwikinews_sample.ndjson")
    info.size = len(payload)
    tar.addfile(info, io.BytesIO(payload))
print("Creato", dest)
