from __future__ import annotations

from corrective_rag.scrubbing.detector import DetectedSpan
from corrective_rag.scrubbing.redactor import redact


class TestNoSpan:
    def test_no_spans_returns_original(self) -> None:
        text = "The Apollo program was a series of space missions."
        result = redact(text, [])
        assert result == text

    def test_empty_text_no_spans(self) -> None:
        assert redact("", []) == ""


class TestSingleSpan:
    def test_single_span_replaced_with_placeholder(self) -> None:
        text = "Contact user@example.invalid for info."
        span = DetectedSpan(start=8, end=28, category="EMAIL", text="user@example.invalid")
        result = redact(text, [span])
        assert result == "Contact [REDACTED:EMAIL] for info."

    def test_placeholder_category_is_uppercased(self) -> None:
        text = "Call +55 11 91234-5678 now."
        span = DetectedSpan(start=5, end=22, category="PHONE", text="+55 11 91234-5678")
        result = redact(text, [span])
        assert "[REDACTED:PHONE]" in result

    def test_characters_around_span_preserved(self) -> None:
        text = "ID: 123.456.789-09 is listed."
        span = DetectedSpan(start=4, end=18, category="GOV_ID", text="123.456.789-09")
        result = redact(text, [span])
        assert result.startswith("ID: ")
        assert result.endswith(" is listed.")

    def test_span_at_start_of_text(self) -> None:
        text = "user@example.invalid is the contact."
        span = DetectedSpan(start=0, end=20, category="EMAIL", text="user@example.invalid")
        result = redact(text, [span])
        assert result == "[REDACTED:EMAIL] is the contact."

    def test_span_at_end_of_text(self) -> None:
        text = "Contact: user@example.invalid"
        span = DetectedSpan(start=9, end=29, category="EMAIL", text="user@example.invalid")
        result = redact(text, [span])
        assert result == "Contact: [REDACTED:EMAIL]"


class TestMultipleSpans:
    def test_two_non_overlapping_spans_both_replaced(self) -> None:
        text = "Email user@example.invalid or call +55 11 91234-5678."
        spans = [
            DetectedSpan(start=6, end=26, category="EMAIL", text="user@example.invalid"),
            DetectedSpan(start=35, end=52, category="PHONE", text="+55 11 91234-5678"),
        ]
        result = redact(text, spans)
        assert "[REDACTED:EMAIL]" in result
        assert "[REDACTED:PHONE]" in result
        assert "user@example.invalid" not in result
        assert "+55 11 91234-5678" not in result

    def test_multiple_spans_order_independent(self) -> None:
        """Redact must produce the same result regardless of input span order."""
        text = "Email user@example.invalid or call +55 11 91234-5678."
        spans_forward = [
            DetectedSpan(start=6, end=26, category="EMAIL", text="user@example.invalid"),
            DetectedSpan(start=35, end=52, category="PHONE", text="+55 11 91234-5678"),
        ]
        spans_reverse = list(reversed(spans_forward))
        assert redact(text, spans_forward) == redact(text, spans_reverse)

    def test_four_categories_all_redacted(self) -> None:
        text = "user@example.invalid +55 11 91234-5678 123.456.789-09 Rua Teste 123 São Paulo"
        from corrective_rag.scrubbing.detector import detect

        spans = detect(text)
        result = redact(text, spans)
        assert "user@example.invalid" not in result
        assert "91234-5678" not in result
        assert "123.456.789-09" not in result
