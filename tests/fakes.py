"""Client Elasticsearch finto: permette di testare l'app web senza un server."""
import json
from types import SimpleNamespace

ARTICLE = {
    "title": "Terremoto in Turchia: centinaia di vittime", "url": "https://it.wikinews.org/wiki/Terremoto",
    "date": "2023-02-06T05:00:00", "category": ["Disastri e incidenti", "Turchia"],
    "lead": "Un forte terremoto ha colpito il sud della Turchia.",
    "body": "Un forte terremoto ha colpito il sud della Turchia.\nLe squadre di soccorso cercano superstiti.",
}
HIT = {"_id": "1002", "_score": 4.2, "_source": ARTICLE,
       "highlight": {"body": ["Un forte <mark>terremoto</mark> ha colpito il sud della Turchia"]}}
RESPONSE = {
    "hits": {"total": {"value": 25, "relation": "eq"}, "hits": [HIT]},
    "aggregations": {
        "categories": {"buckets": [{"key": "Disastri e incidenti", "doc_count": 2}, {"key": "Turchia", "doc_count": 1}]},
        "years": {"buckets": [{"key": "2023", "doc_count": 1}]},
    },
}
EMPTY = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}, "aggregations": {}}


class FakeES:
    def __init__(self, reachable=True, index_exists=True):
        self.reachable, self.calls = reachable, []
        self.indices = SimpleNamespace(exists=lambda index: index_exists)

    def ping(self):
        return self.reachable

    def count(self, index):
        return {"count": 11}

    def search(self, index, **kwargs):
        self.calls.append(kwargs)
        query = kwargs.get("query", {})
        if "ids" in query:
            return {"hits": {"total": {"value": 1}, "hits": [{"_id": "1002", "_source": ARTICLE}]}} \
                if "1002" in query["ids"]["values"] else EMPTY
        if "xyzqwerty" in json.dumps(query):
            return EMPTY
        if kwargs.get("from_", 0) >= 250:  # pagina oltre la fine
            return {**RESPONSE, "hits": {"total": {"value": 25, "relation": "eq"}, "hits": []}}
        return RESPONSE
