from __future__ import annotations

import json
from pathlib import Path

from corrective_rag.scrubbing.audit import PiiScanRecord, append_audit, write_eval_results


class TestPiiScanRecord:
    def test_serializes_to_expected_json_shape(self) -> None:
        record = PiiScanRecord(
            chunk_id="abc123",
            categories_detected=["EMAIL", "PHONE"],
            action_taken="redacted",
            scan_timestamp="2026-08-24T12:00:00Z",
        )
        data = record.to_dict()
        assert data["chunk_id"] == "abc123"
        assert data["categories_detected"] == ["EMAIL", "PHONE"]
        assert data["action_taken"] == "redacted"
        assert data["scan_timestamp"] == "2026-08-24T12:00:00Z"

    def test_clean_record_serializes_correctly(self) -> None:
        record = PiiScanRecord(
            chunk_id="xyz789",
            categories_detected=[],
            action_taken="clean",
            scan_timestamp="2026-08-24T12:01:00Z",
        )
        data = record.to_dict()
        assert data["categories_detected"] == []
        assert data["action_taken"] == "clean"

    def test_categories_detected_is_list_in_json(self) -> None:
        record = PiiScanRecord(
            chunk_id="c1",
            categories_detected=["GOV_ID"],
            action_taken="redacted",
            scan_timestamp="2026-08-24T00:00:00Z",
        )
        raw = json.dumps(record.to_dict())
        parsed = json.loads(raw)
        assert isinstance(parsed["categories_detected"], list)


class TestAppendAudit:
    def test_appends_valid_jsonl_line(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        record = PiiScanRecord(
            chunk_id="c1",
            categories_detected=[],
            action_taken="clean",
            scan_timestamp="2026-08-24T00:00:00Z",
        )
        append_audit(record, audit_file)
        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["chunk_id"] == "c1"

    def test_creates_parent_dirs_if_absent(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "nested" / "deep" / "audit.jsonl"
        record = PiiScanRecord(
            chunk_id="c1",
            categories_detected=[],
            action_taken="clean",
            scan_timestamp="2026-08-24T00:00:00Z",
        )
        append_audit(record, audit_file)
        assert audit_file.exists()

    def test_two_records_produce_two_lines(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        for chunk_id in ("c1", "c2"):
            record = PiiScanRecord(
                chunk_id=chunk_id,
                categories_detected=[],
                action_taken="clean",
                scan_timestamp="2026-08-24T00:00:00Z",
            )
            append_audit(record, audit_file)
        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 2
        ids = [json.loads(line)["chunk_id"] for line in lines]
        assert ids == ["c1", "c2"]

    def test_appends_not_overwrites(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        for chunk_id in ("c1", "c2", "c3"):
            append_audit(
                PiiScanRecord(
                    chunk_id=chunk_id,
                    categories_detected=[],
                    action_taken="clean",
                    scan_timestamp="2026-08-24T00:00:00Z",
                ),
                audit_file,
            )
        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 3


class TestWriteEvalResults:
    def test_writes_json_with_required_keys(self, tmp_path: Path) -> None:
        results_file = tmp_path / "eval_results.json"
        write_eval_results(
            {
                "sc003_pass": True,
                "sc004_pass": True,
                "sc005_pass": False,
                "run_timestamp": "2026-08-24T00:00:00Z",
            },
            results_file,
        )
        data = json.loads(results_file.read_text())
        assert data["sc003_pass"] is True
        assert data["sc004_pass"] is True
        assert data["sc005_pass"] is False
        assert "run_timestamp" in data

    def test_creates_parent_dirs_if_absent(self, tmp_path: Path) -> None:
        results_file = tmp_path / "subdir" / "eval_results.json"
        write_eval_results(
            {"sc003_pass": True, "sc004_pass": True, "sc005_pass": True, "run_timestamp": ""},
            results_file,
        )
        assert results_file.exists()
