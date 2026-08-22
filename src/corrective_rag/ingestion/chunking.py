from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_CHUNK_LENGTH = 50

# Wikipedia's explaintext extract keeps MediaWiki section headers as plain
# text (e.g. "== Name ==", "=== Origins ==="), which is layout markup, not
# prose — strip it before chunking so it never pollutes an embedded chunk.
_SECTION_HEADER_RE = re.compile(r"^=+[^=\n]+=+\s*$", re.MULTILINE)

# The splitter's chunk_overlap can start a chunk mid-way through the previous
# chunk's trailing punctuation (e.g. ". Next sentence…") since char-based
# overlap doesn't align to sentence starts. Trim it off after splitting.
_LEADING_PUNCTUATION_RE = re.compile(r"^[.,;:!?)\]]+\s*")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_document_id: str
    chunk_index: int
    text: str


def _make_chunk_id(source_document_id: str, chunk_index: int, text: str) -> str:
    digest_input = f"{source_document_id}|{chunk_index}|{text}".encode()
    return hashlib.sha256(digest_input).hexdigest()[:16]


def split_into_chunks(source_document_id: str, text: str) -> list[Chunk]:
    cleaned_text = _SECTION_HEADER_RE.sub("", text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    raw_chunks = [
        stripped
        for piece in splitter.split_text(cleaned_text)
        if (stripped := _LEADING_PUNCTUATION_RE.sub("", piece.strip()).strip())
        and len(stripped) >= MIN_CHUNK_LENGTH
    ]

    return [
        Chunk(
            chunk_id=_make_chunk_id(source_document_id, index, chunk_text),
            source_document_id=source_document_id,
            chunk_index=index,
            text=chunk_text,
        )
        for index, chunk_text in enumerate(raw_chunks)
    ]
