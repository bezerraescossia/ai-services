from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PiiScanRecord:
    chunk_id: str
    categories_detected: list[str]
    action_taken: Literal["clean", "redacted"]
    scan_timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def append_audit(record: PiiScanRecord, path: Path) -> None:
    """Append *record* as a JSON line to *path*, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict()) + "\n")


def write_eval_results(results: dict, path: Path) -> None:
    """Write *results* as a JSON file to *path*, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
