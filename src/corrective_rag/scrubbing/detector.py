from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedSpan:
    start: int
    end: int
    category: str
    text: str


# ---------------------------------------------------------------------------
# Compiled patterns — all four resolved flaggable categories (FR-001).
# Ordered from most-specific to least to minimise false positives when multiple
# patterns could overlap on the same token.
# ---------------------------------------------------------------------------

# CPF: 123.456.789-09
_CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

# RG (common São Paulo format): 12.345.678-9 or 12.345.678-X
_RG_RE = re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-[\dX]\b", re.IGNORECASE)

# US SSN: 123-45-6789
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Email — RFC-5322-lite; must compile before phone to avoid matching domain parts
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)*\.[a-zA-Z]{2,}", re.IGNORECASE)

# Phone — three formats accepted (all require word boundaries to avoid matching
# years, catalog numbers, or other numeric runs):
#   1. With country code and/or parens: +55 11 91234-5678 / (11) 91234-5678
#   2. NANP 3-3-4: 212-555-0199 / 555.123.4567 (three groups with separators)
#   3. BR local 4-5 digit + separator + 4 digit: 9123-4567
#
# SSN (3-2-4) is caught by _SSN_RE first and claimed before _PHONE_RE runs,
# so there is no cross-pattern overlap on 3-*-4 tokens.
_PHONE_NANP_RE = re.compile(
    r"(?<!\d)\d{3}[.\-\s]\d{3}[.\-\s]\d{4}(?!\d)",
)

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+\d{1,3}[\s\-]?)?"  # optional country code
    r"(?:\(\d{2,4}\)[\s\-]?)?"  # optional area code in parens
    r"\d{4,5}[\s\-]\d{4}"  # local number with separator
    r"(?!\d)",
)

# Physical address — street keyword + number.
# Covers Portuguese (Rua, Avenida, Av., Alameda, Travessa) and English (Street, Avenue, Road, Blvd).
# Two orderings:
#   keyword-first: "Rua das Flores 123" — keyword → words → number
#   number-first:  "42 Elm Street" / "42 Elm St."  — number → words → keyword
#
# Abbreviated keywords (St., Rd., Ave., Blvd.) are restricted to the number-first branch.
# In the keyword-first branch they cause too many false positives (e.g. "rd. While ... 18")
# because they appear as ordinary sentence abbreviations followed by unrelated numbers.
_ADDRESS_KEYWORD_FULL = r"(?:Rua|Avenida|Alameda|Travessa|Street|Avenue|Road|Boulevard)"
_ADDRESS_KEYWORD_ALL = (
    r"(?:Rua|Avenida|Av\.|Alameda|Travessa|Street|St\.|Avenue|Ave\.|Road|Rd\.|Boulevard|Blvd\.)"
)
_ADDRESS_RE = re.compile(
    # keyword-first: full keyword only, max ~30 chars between keyword and trailing number
    rf"(?:{_ADDRESS_KEYWORD_FULL}\s+[\w\s]{{1,30}}\s+\d{{1,6}}"
    rf"|"
    # number-first: abbreviations allowed, max 5 intervening words
    rf"\d{{1,6}}(?:\s+\w+){{0,5}}\s+{_ADDRESS_KEYWORD_ALL})",
    re.IGNORECASE,
)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_CPF_RE, "GOV_ID"),
    (_RG_RE, "GOV_ID"),
    (_SSN_RE, "GOV_ID"),
    (_EMAIL_RE, "EMAIL"),
    (_PHONE_NANP_RE, "PHONE"),
    (_PHONE_RE, "PHONE"),
    (_ADDRESS_RE, "ADDRESS"),
]


def detect(text: str) -> list[DetectedSpan]:
    """Return all detected PII spans in *text*, sorted by start offset ascending.

    Each span is non-overlapping: once a character position is claimed by a
    higher-priority pattern it is excluded from lower-priority scans.
    """
    if not text:
        return []

    claimed: set[int] = set()
    spans: list[DetectedSpan] = []

    for pattern, category in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            # Skip if any position in this match is already claimed
            match_positions = set(range(start, end))
            if match_positions & claimed:
                continue
            claimed |= match_positions
            spans.append(DetectedSpan(start=start, end=end, category=category, text=match.group()))

    return sorted(spans, key=lambda s: s.start)
