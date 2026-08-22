from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

# Wikipedia's API etiquette policy rejects requests with no (or a generic)
# User-Agent header: https://meta.wikimedia.org/wiki/User-Agent_policy
WIKIPEDIA_USER_AGENT = (
    "corrective-rag-ingestion/0.1 (https://github.com/anthropics/ai-services; "
    "contact: bezerraescossia@gmail.com)"
)


class WikipediaFetchError(Exception):
    def __init__(self, title: str, reason: str) -> None:
        self.title = title
        super().__init__(f"Failed to fetch Wikipedia article {title!r}: {reason}")


@dataclass(frozen=True)
class FetchedArticle:
    title: str
    extract_text: str
    fetched_at: str


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_raw(client: httpx.Client, title: str) -> httpx.Response:
    response = client.get(
        WIKIPEDIA_API_URL,
        headers={"User-Agent": WIKIPEDIA_USER_AGENT},
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": 1,
            "redirects": 1,
            "titles": title,
        },
    )
    response.raise_for_status()
    return response


def fetch_article(client: httpx.Client, title: str) -> FetchedArticle:
    try:
        response = _fetch_raw(client, title)
    except (httpx.TransportError, httpx.HTTPStatusError) as exc:
        raise WikipediaFetchError(title, str(exc)) from exc

    payload = response.json()
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    if page is None or "missing" in page or not page.get("extract"):
        raise WikipediaFetchError(title, "article not found or has no extract")

    return FetchedArticle(
        title=title,
        extract_text=page["extract"],
        fetched_at=dt.datetime.now(dt.UTC).isoformat(),
    )


def fetch_articles(client: httpx.Client, titles: list[str]) -> list[FetchedArticle]:
    return [fetch_article(client, title) for title in titles]
