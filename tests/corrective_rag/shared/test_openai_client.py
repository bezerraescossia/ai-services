from types import SimpleNamespace

from corrective_rag.shared.openai_client import embed_text


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
