from types import SimpleNamespace

from corrective_rag.shared.openai_client import embed_text, embed_text_with_usage


class _FakeEmbeddings:
    def create(self, *, model: str, input: str):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(total_tokens=7),
        )


class _FakeOpenAI:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddings()


def test_embed_text_returns_the_embedding_vector():
    vector = embed_text(_FakeOpenAI(), "Apollo 11 was the spaceflight...")

    assert vector == [0.1, 0.2, 0.3]


def test_embed_text_logs_token_usage_and_cost(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="corrective_rag.shared.openai_client"):
        embed_text(_FakeOpenAI(), "Apollo 11 was the spaceflight...")

    assert any("openai_embedding_call" in record.message for record in caplog.records)


def test_embed_text_with_usage_returns_vector_and_usage():
    result = embed_text_with_usage(_FakeOpenAI(), "Apollo 11 was the spaceflight...")

    assert result.vector == [0.1, 0.2, 0.3]
    assert result.tokens_used == 7
    assert result.estimated_cost_usd == (7 / 1000) * 0.00002


def test_embed_text_with_usage_logs_token_usage_and_cost(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="corrective_rag.shared.openai_client"):
        embed_text_with_usage(_FakeOpenAI(), "Apollo 11 was the spaceflight...")

    assert any("openai_embedding_call" in record.message for record in caplog.records)
