from __future__ import annotations

from corrective_rag.scrubbing.detector import DetectedSpan


def redact(text: str, spans: list[DetectedSpan]) -> str:
    """Replace each detected span in *text* with ``[REDACTED:<CATEGORY>]``.

    Spans are processed right-to-left (highest start offset first) so earlier
    offsets remain valid after each replacement.  Input span order is irrelevant.
    """
    if not spans:
        return text

    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        placeholder = f"[REDACTED:{span.category.upper()}]"
        text = text[: span.start] + placeholder + text[span.end :]

    return text
