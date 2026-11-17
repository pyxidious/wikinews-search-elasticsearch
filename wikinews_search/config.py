import os
from pathlib import Path

DEFAULT_DUMP_URL = (
    "https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/"
    "itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz"
)
DEFAULT_DUMP_PATH = Path("data") / DEFAULT_DUMP_URL.rsplit("/", 1)[-1]
DEFAULT_ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
DEFAULT_INDEX = os.environ.get("ES_INDEX", "itwikinews")
PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
MAX_WINDOW = 10_000  # limite di Elasticsearch: from + size <= index.max_result_window
