"""Lever postings API: https://api.lever.co/v0/postings/{account}?mode=json"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register
from .greenhouse import html_to_text


@register
class LeverCollector(Collector):
    name = "lever"

    def collect(self, company: CompanyConfig) -> list[Job]:
        account = company.source_ref
        if not account:
            raise FetchError("lever collector needs source_ref (account name)")
        url = f"https://api.lever.co/v0/postings/{account}?mode=json"
        postings = json.loads(self.client.get(url))
        jobs: list[Job] = []
        for p in postings:
            categories = p.get("categories") or {}
            created = p.get("createdAt")
            date_posted = (
                datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                if created else None
            )
            description = html_to_text(
                (p.get("description") or "") + " " +
                " ".join(html_to_text(l.get("content", "")) if isinstance(l, dict) else str(l)
                         for l in p.get("lists", []))
            ) or None
            workplace = p.get("workplaceType")
            jobs.append(Job(
                job_id=f"lever:{account}:{p.get('id')}",
                company=company.company,
                title=(p.get("text") or "").strip(),
                location=categories.get("location"),
                job_url=p.get("hostedUrl"),
                description=description,
                date_posted=date_posted,
                source="lever",
                collected_at=now_iso(),
                department=categories.get("team") or categories.get("department"),
                employment_type=categories.get("commitment"),
                remote_status="Remote" if workplace == "remote" else
                              "Hybrid" if workplace == "hybrid" else None,
            ))
        return jobs
