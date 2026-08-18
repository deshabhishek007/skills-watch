"""Workable public widget API: https://apply.workable.com/api/v3/accounts/{account}/jobs"""

from __future__ import annotations

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register
from .greenhouse import html_to_text

MAX_PAGES = 20


@register
class WorkableCollector(Collector):
    name = "workable"

    def collect(self, company: CompanyConfig) -> list[Job]:
        account = company.source_ref
        if not account:
            raise FetchError("workable collector needs source_ref (account name)")
        base = f"https://apply.workable.com/api/v3/accounts/{account}"
        jobs: list[Job] = []
        token = None
        for _ in range(MAX_PAGES):
            body: dict = {"query": "", "location": [], "department": [], "worktype": [], "remote": []}
            if token:
                body["token"] = token
            data = self.client.post_json(f"{base}/jobs", body,
                                         headers={"Accept": "application/json"})
            for j in data.get("results", []):
                shortcode = j.get("shortcode")
                description = None
                try:
                    detail = self.client.get_json(f"{base}/jobs/{shortcode}",
                                                  headers={"Accept": "application/json"})
                    parts = [detail.get("description") or "", detail.get("requirements") or "",
                             detail.get("benefits") or ""]
                    description = html_to_text(" ".join(parts)) or None
                except FetchError:
                    pass
                loc = j.get("location") or {}
                jobs.append(Job(
                    job_id=f"workable:{account}:{shortcode}",
                    company=company.company,
                    title=(j.get("title") or "").strip(),
                    location=", ".join(x for x in [loc.get("city"), loc.get("country")] if x) or None,
                    job_url=f"https://apply.workable.com/{account}/j/{shortcode}/" if shortcode else None,
                    description=description,
                    date_posted=j.get("published"),
                    source="workable",
                    collected_at=now_iso(),
                    department=(j.get("department") or [None])[0] if isinstance(j.get("department"), list) else j.get("department"),
                    employment_type=j.get("type"),
                    remote_status="Remote" if j.get("remote") else None,
                ))
            token = data.get("nextPage")
            if not token:
                break
        return jobs
