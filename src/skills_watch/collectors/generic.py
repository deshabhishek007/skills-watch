"""Best-effort collector for custom careers pages.

Strategy: fetch the careers page, find links that look like individual job
postings, fetch each one, and extract title + readable text. Also detects
embedded ATS boards (Greenhouse/Lever/Ashby/Workable iframes or links) and
reports them so the company can be upgraded to a structured collector.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register

JOB_LINK_HINT = re.compile(
    r"(job|career|position|opening|vacanc|role|apply|join)", re.IGNORECASE
)
EMBEDDED_ATS = re.compile(
    r"(boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.lever\.co|"
    r"jobs\.ashbyhq\.com|apply\.workable\.com|\w+\.bamboohr\.com|"
    r"myworkdayjobs\.com|jobs\.smartrecruiters\.com|\w+\.recruitee\.com)/([\w-]+)",
)
MAX_POSTINGS = 60
# Nav/footer links that match JOB_LINK_HINT but aren't postings
BORING_PATHS = re.compile(r"^/?(#|$)|(privacy|terms|login|signin|blog|about)", re.IGNORECASE)


class EmbeddedATSFound(FetchError):
    """Raised when the page just embeds a known ATS — upgrade source_type instead."""

    def __init__(self, ats_host: str, ref: str):
        super().__init__(f"page embeds ATS {ats_host} (ref: {ref}) — set source_type accordingly")
        self.ats_host = ats_host
        self.ref = ref


@register
class GenericCollector(Collector):
    name = "generic"

    def collect(self, company: CompanyConfig) -> list[Job]:
        if not company.careers_url:
            raise FetchError("no careers_url configured")
        page = self.client.get(company.careers_url)

        m = EMBEDDED_ATS.search(page)
        if m:
            raise EmbeddedATSFound(m.group(1), m.group(2))

        soup = BeautifulSoup(page, "html.parser")
        base_host = urlparse(company.careers_url).netloc
        seen: set[str] = set()
        candidates: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = urljoin(company.careers_url, a["href"]).split("#")[0]
            text = a.get_text(" ", strip=True)
            parsed = urlparse(href)
            if parsed.netloc != base_host or href in seen:
                continue
            if href.rstrip("/") == company.careers_url.rstrip("/"):
                continue
            if BORING_PATHS.search(parsed.path):
                continue
            if JOB_LINK_HINT.search(parsed.path) or JOB_LINK_HINT.search(text):
                seen.add(href)
                candidates.append((href, text))

        jobs: list[Job] = []
        for href, link_text in candidates[:MAX_POSTINGS]:
            try:
                posting = self.client.get(href)
            except FetchError:
                continue
            psoup = BeautifulSoup(posting, "html.parser")
            h1 = psoup.find("h1")
            title = (h1.get_text(" ", strip=True) if h1 else link_text).strip()
            if not title or len(title) > 120:
                continue
            body = psoup.get_text(" ", strip=True)
            # A real posting has substantial text; listing/nav pages get skipped
            # by requiring job-ish vocabulary in the body.
            if len(body) < 400 or not re.search(
                r"(responsibilit|requirement|qualificat|what you.ll do|about the role|"
                r"we are looking|experience with)", body, re.IGNORECASE
            ):
                continue
            jobs.append(Job(
                job_id=f"generic:{company.company}:{href}",
                company=company.company,
                title=title,
                location=None,
                job_url=href,
                description=body[:20000],
                date_posted=None,
                source="generic",
                collected_at=now_iso(),
            ))
        return jobs
