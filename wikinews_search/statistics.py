"""Contatori condivisi dalla lettura streaming e dall'indicizzazione."""
from collections import Counter
from dataclasses import asdict, dataclass, field


@dataclass
class IndexStats:
    records_read: int = 0
    valid_articles: int = 0
    discarded: Counter = field(default_factory=Counter)
    indexed_operations: int = 0
    indexed_documents: int | None = None
    indexing_errors: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self):
        result = asdict(self)
        result["discarded"] = dict(self.discarded)
        return result
