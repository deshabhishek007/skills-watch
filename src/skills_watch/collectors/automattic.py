"""Automattic's work-with-us page embeds its Greenhouse job list as inline JSON
(`const ghJobsData = [...]`); individual job pages are static HTML. No public
Greenhouse board endpoint exists, so this adapter reads the embedded data."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register

LISTING_URL = "https://automattic.com/work-with-us/jobs/"
JOB_URL = "https://automattic.com/work-with-us/job/{slug}/"
DATA_RX = re.compile(r"const ghJobsData\s*=\s*(?=\[)")


@register
class AutomatticCollector(Collector):
    name = "automattic"

    def collect(self, company: CompanyConfig) -> list[Job]:
        page = self.client.get(company.careers_url or LISTING_URL)
        m = DATA_RX.search(page)
        if not m:
            raise FetchError("ghJobsData block not found on work-with-us page "
                             "(page structure changed?)")
        try:
            data, _ = json.JSONDecoder().raw_decode(page, m.end())
        except json.JSONDecodeError as e:
            raise FetchError(f"could not parse ghJobsData JSON: {e}") from e
        jobs: list[Job] = []
        for j in data:
            slug = j.get("slug")
            url = JOB_URL.format(slug=slug) if slug else None
            description = None
            if url:
                try:
                    soup = BeautifulSoup(self.client.get(url), "html.parser")
                    main = soup.find("main") or soup.body
                    description = main.get_text(" ", strip=True)[:20000] if main else None
                except FetchError:
                    pass
            meta = j.get("metadata") or {}
            team = meta.get("Team")
            jobs.append(Job(
                job_id=f"greenhouse:automattic:{j.get('id')}",
                company=company.company,
                title=(j.get("title") or "").strip(),
                location=meta.get("Location"),
                job_url=url,
                description=description,
                date_posted=None,
                source="automattic",
                collected_at=now_iso(),
                department=", ".join(team) if isinstance(team, list) else team,
            ))
        return jobs
