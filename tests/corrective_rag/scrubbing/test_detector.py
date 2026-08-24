from __future__ import annotations

from corrective_rag.scrubbing.detector import DetectedSpan, detect


class TestEmail:
    def test_detects_simple_email(self) -> None:
        text = "Contact me at user@example.invalid for details."
        spans = detect(text)
        assert len(spans) == 1
        assert spans[0].category == "EMAIL"
        assert spans[0].text == "user@example.invalid"

    def test_detects_email_with_plus(self) -> None:
        text = "Send to user+tag@sub.domain.invalid please."
        spans = detect(text)
        assert any(s.category == "EMAIL" for s in spans)

    def test_detects_multiple_emails(self) -> None:
        text = "Email a@b.invalid or c@d.invalid for help."
        spans = detect(text)
        emails = [s for s in spans if s.category == "EMAIL"]
        assert len(emails) == 2


class TestPhone:
    def test_detects_br_phone_with_ddd(self) -> None:
        text = "Call us at +55 11 91234-5678 for support."
        spans = detect(text)
        assert any(s.category == "PHONE" for s in spans)

    def test_detects_us_phone(self) -> None:
        text = "Reach us at 212-555-0199 anytime."
        spans = detect(text)
        assert any(s.category == "PHONE" for s in spans)

    def test_detects_phone_with_parentheses(self) -> None:
        text = "Call (11) 91234-5678 to schedule."
        spans = detect(text)
        assert any(s.category == "PHONE" for s in spans)


class TestPhysicalAddress:
    def test_detects_rua_address(self) -> None:
        text = "He lives at Rua das Flores 123, São Paulo."
        spans = detect(text)
        assert any(s.category == "ADDRESS" for s in spans)

    def test_detects_avenida_address(self) -> None:
        text = "Visit us at Avenida Paulista 1000, São Paulo."
        spans = detect(text)
        assert any(s.category == "ADDRESS" for s in spans)

    def test_detects_street_address(self) -> None:
        text = "Office at 42 Elm Street, Springfield."
        spans = detect(text)
        assert any(s.category == "ADDRESS" for s in spans)


class TestGovernmentID:
    def test_detects_cpf(self) -> None:
        text = "The document lists CPF 123.456.789-09 as owner."
        spans = detect(text)
        assert any(s.category == "GOV_ID" for s in spans)

    def test_detects_rg(self) -> None:
        text = "RG 12.345.678-9 was presented at the registry."
        spans = detect(text)
        assert any(s.category == "GOV_ID" for s in spans)

    def test_detects_ssn(self) -> None:
        text = "SSN 123-45-6789 appeared in the record."
        spans = detect(text)
        assert any(s.category == "GOV_ID" for s in spans)


class TestSubjectExclusion:
    def test_person_name_alone_is_clean(self) -> None:
        text = "Buzz Aldrin was the second person to walk on the Moon."
        spans = detect(text)
        assert spans == []

    def test_encyclopedic_biographical_text_is_clean(self) -> None:
        text = (
            "Neil Armstrong, born in 1930, was an American astronaut "
            "and the first person to walk on the Moon on July 20, 1969."
        )
        spans = detect(text)
        assert spans == []


class TestAmbiguousToken:
    def test_ambiguous_gov_id_like_token_is_flagged(self) -> None:
        """A token that matches the gov-ID pattern must be flagged even if
        in-domain ambiguity exists — spec Edge Cases: err toward safer default."""
        text = "The record shows ID 123.456.789-09 in the system."
        spans = detect(text)
        assert any(s.category == "GOV_ID" for s in spans)


class TestMultiSpan:
    def test_multiple_categories_in_one_chunk(self) -> None:
        text = (
            "Contact: user@example.invalid, +55 11 91234-5678, "
            "CPF 123.456.789-09, Rua Teste 123 São Paulo."
        )
        spans = detect(text)
        categories = {s.category for s in spans}
        assert "EMAIL" in categories
        assert "PHONE" in categories
        assert "GOV_ID" in categories
        assert "ADDRESS" in categories

    def test_spans_ordered_by_start_offset(self) -> None:
        text = "Email user@example.invalid and call +55 11 91234-5678."
        spans = detect(text)
        offsets = [s.start for s in spans]
        assert offsets == sorted(offsets)


class TestEmptyAndClean:
    def test_empty_string_returns_empty(self) -> None:
        assert detect("") == []

    def test_clean_text_returns_empty(self) -> None:
        text = "The Apollo program was a human spaceflight program undertaken by NASA."
        assert detect(text) == []


class TestDetectedSpanShape:
    def test_span_has_correct_bounds(self) -> None:
        text = "Email me at user@example.invalid please."
        spans = detect(text)
        assert len(spans) == 1
        span = spans[0]
        assert isinstance(span, DetectedSpan)
        assert span.start == text.index("user@example.invalid")
        assert span.end == span.start + len("user@example.invalid")
        assert span.text == "user@example.invalid"
        assert span.category == "EMAIL"
