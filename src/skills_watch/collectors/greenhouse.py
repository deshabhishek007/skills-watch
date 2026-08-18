"""Greenhouse job board API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs"""

from __future__ import annotations

import html

from bs4 import BeautifulSoup

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register


def html_to_text(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)


@register
class GreenhouseCollector(Collector):
    name = "greenhouse"

    def collect(self, company: CompanyConfig) -> list[Job]:
        token = company.source_ref
        if not token:
            raise FetchError("greenhouse collector needs source_ref (board token)")
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        data = self.client.get_json(url)
        jobs = []
        for j in data.get("jobs", []):
            content = j.get("content") or ""
            # Greenhouse double-escapes the job content HTML
            description = html_to_text(html.unescape(content)) or None
            departments = j.get("departments") or []
            jobs.append(Job(
                job_id=f"greenhouse:{token}:{j['id']}",
                company=company.company,
                title=j.get("title", "").strip(),
                location=(j.get("location") or {}).get("name"),
                job_url=j.get("absolute_url"),
                description=description,
                date_posted=(j.get("first_published") or j.get("updated_at") or None),
                source="greenhouse",
                collected_at=now_iso(),
                department=departments[0].get("name") if departments else None,
            ))
        return jobs
