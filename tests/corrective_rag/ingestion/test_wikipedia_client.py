import httpx
import pytest

from corrective_rag.ingestion.wikipedia_client import (
    WikipediaFetchError,
    fetch_article,
    fetch_articles,
)


def test_persistent_server_error_raises_with_article_title():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(WikipediaFetchError) as exc_info:
        fetch_article(client, "Apollo 11")

    assert exc_info.value.title == "Apollo 11"


def test_persistent_server_error_retries_before_raising():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(WikipediaFetchError):
        fetch_article(client, "Apollo 11")

    assert len(calls) > 1


def test_missing_article_raises_without_retry():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"query": {"pages": {"-1": {"missing": "", "title": "Nonexistent Article"}}}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(WikipediaFetchError) as exc_info:
        fetch_article(client, "Nonexistent Article")

    assert exc_info.value.title == "Nonexistent Article"
    assert len(calls) == 1


def test_successful_fetch_returns_extract_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "18426568": {
                            "title": "Apollo 11",
                            "extract": (
                                "Apollo 11 was the spaceflight that first landed humans "
                                "on the Moon."
                            ),
                        }
                    }
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    article = fetch_article(client, "Apollo 11")

    assert article.title == "Apollo 11"
    assert "Apollo 11" in article.extract_text
    assert article.fetched_at


def test_fetch_articles_aggregates_multiple_titles():
    extracts = {"Apollo 11": "Apollo 11 text", "Voyager 1": "Voyager 1 text"}

    def handler(request: httpx.Request) -> httpx.Response:
        title = request.url.params["titles"]
        return httpx.Response(
            200,
            json={"query": {"pages": {"1": {"title": title, "extract": extracts[title]}}}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    articles = fetch_articles(client, list(extracts))

    assert [a.title for a in articles] == list(extracts)
    assert [a.extract_text for a in articles] == list(extracts.values())
