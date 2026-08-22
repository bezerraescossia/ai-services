from corrective_rag.ingestion.chunking import split_into_chunks

SAMPLE_TEXT = (
    "Apollo 11 was the spaceflight that first landed humans on the Moon. "
    "Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin formed the American crew "
    "that landed the Apollo Lunar Module Eagle on July 20, 1969.\n\n"
    "Michael Collins piloted the Command Module Columbia alone in lunar orbit while they were "
    "on the Moon's surface. Armstrong and Aldrin spent about two and a quarter hours together "
    "outside the spacecraft, and they collected 47.5 pounds (21.5 kg) of lunar material.\n\n"
) * 5


def test_split_produces_multiple_chunks_with_no_empty_or_near_empty_chunks():
    chunks = split_into_chunks("Apollo 11", SAMPLE_TEXT)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.strip() != ""
        assert len(chunk.text) >= 50
        assert chunk.source_document_id == "Apollo 11"


def test_chunk_ids_are_sequential_and_deterministic():
    first_pass = split_into_chunks("Apollo 11", SAMPLE_TEXT)
    second_pass = split_into_chunks("Apollo 11", SAMPLE_TEXT)

    assert [c.chunk_id for c in first_pass] == [c.chunk_id for c in second_pass]
    assert [c.chunk_index for c in first_pass] == list(range(len(first_pass)))


def test_chunk_id_differs_for_different_source_document():
    chunks_a = split_into_chunks("Apollo 11", SAMPLE_TEXT)
    chunks_b = split_into_chunks("Voyager 1", SAMPLE_TEXT)

    assert chunks_a[0].chunk_id != chunks_b[0].chunk_id


def test_short_text_is_not_fragmented_into_near_empty_pieces():
    text = "Short text that is still one whole paragraph, well above the minimum chunk length."
    chunks = split_into_chunks("Tiny Article", text)

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_mediawiki_section_headers_are_stripped_before_chunking():
    text = (
        "== Name ==\n"
        "The program was named after the Greek god Apollo by NASA manager Abe Silverstein. "
        "He chose the name because Apollo, riding his chariot across the Sun, was to him "
        "a fitting symbol of the grand scale of the new program.\n\n"
        "=== Origins ===\n"
        "In July 1960, NASA administrator T. Keith Glennan announced the Apollo program to "
        "industry representatives at a series of Space Task Group conferences.\n\n"
    ) * 3
    chunks = split_into_chunks("Apollo program", text)

    for chunk in chunks:
        assert "==" not in chunk.text


def test_chunks_do_not_start_with_leading_punctuation_from_overlap():
    text = (
        "Apollo 11 was the spaceflight that first landed humans on the Moon. "
        "Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin formed the American crew "
        "that landed the Apollo Lunar Module Eagle on July 20, 1969. "
        "Michael Collins piloted the Command Module Columbia alone in lunar orbit while they "
        "were on the Moon's surface. Armstrong and Aldrin spent about two and a quarter hours "
        "together outside the spacecraft, and they collected 47.5 pounds of lunar material. "
    ) * 5
    chunks = split_into_chunks("Apollo 11", text)

    for chunk in chunks:
        assert chunk.text[0].isalnum() or chunk.text[0] in "\"'("
