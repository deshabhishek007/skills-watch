"""Collector base: polite HTTP (rate-limited, cached, honest UA) and a registry.

Ethics: official sources only, no auth bypass, no CAPTCHA circumvention. A source
that can't be collected politely is reported as failed/unsupported — never scraped
harder.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import requests

from ..models import CompanyConfig, Job

USER_AGENT = "skills-watch/0.1 (open-source hiring research; +https://github.com/deshabhishek007/skills-watch)"
REQUEST_DELAY_SECONDS = 1.5
TIMEOUT_SECONDS = 30


class FetchError(Exception):
    pass


class HttpClient:
    """Rate-limited, disk-cached HTTP client shared by all collectors.

    The cache is keyed by URL+body and scoped to one calendar day, so re-runs on
    the same day don't re-hit employers' sites.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.cache_dir = cache_dir
        self._last_request = 0.0

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.cache_dir / day / f"{digest}.json"

    def request(self, method: str, url: str, *, json_body: dict | None = None,
                headers: dict | None = None) -> str:
        key = f"{method} {url} {json.dumps(json_body, sort_keys=True) if json_body else ''}"
        cache_path = self._cache_path(key)
        if cache_path and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        wait = REQUEST_DELAY_SECONDS - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.request(method, url, json=json_body, headers=headers,
                                        timeout=TIMEOUT_SECONDS)
        except requests.RequestException as e:
            self._last_request = time.monotonic()
            raise FetchError(f"{type(e).__name__}: {e}") from e
        self._last_request = time.monotonic()
        if resp.status_code != 200:
            raise FetchError(f"HTTP {resp.status_code} for {url}")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(resp.text, encoding="utf-8")
        return resp.text

    def get(self, url: str, headers: dict | None = None) -> str:
        return self.request("GET", url, headers=headers)

    def get_json(self, url: str, headers: dict | None = None) -> dict:
        return json.loads(self.get(url, headers=headers))

    def post_json(self, url: str, body: dict, headers: dict | None = None) -> dict:
        return json.loads(self.request("POST", url, json_body=body, headers=headers))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Collector(ABC):
    """A collector turns one CompanyConfig into a list of Jobs in the common schema."""

    name: str

    def __init__(self, client: HttpClient):
        self.client = client

    @abstractmethod
    def collect(self, company: CompanyConfig) -> list[Job]:
        """Return open jobs. Raise FetchError on collection failure."""


COLLECTORS: dict[str, type[Collector]] = {}


def register(cls: type[Collector]) -> type[Collector]:
    COLLECTORS[cls.name] = cls
    return cls


def get_collector(source_type: str, client: HttpClient) -> Collector | None:
    cls = COLLECTORS.get(source_type)
    return cls(client) if cls else None
