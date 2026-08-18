"""Workday CXS API: POST https://{host}/wday/cxs/{tenant}/{site}/jobs

source_ref format: "{host}|{site}", e.g. "godaddy.wd1.myworkdayjobs.com|GoDaddy".
The tenant is the first label of the host.
"""

from __future__ import annotations

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register
from .greenhouse import html_to_text

PAGE_SIZE = 20
MAX_JOBS = 400  # safety cap for very large employers


@register
class WorkdayCollector(Collector):
    name = "workday"

    def collect(self, company: CompanyConfig) -> list[Job]:
        ref = company.source_ref or ""
        if "|" not in ref:
            raise FetchError('workday collector needs source_ref "host|site"')
        host, site = ref.split("|", 1)
        tenant = host.split(".")[0]
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        jobs: list[Job] = []
        offset = 0
        total = None
        while total is None or (offset < total and offset < MAX_JOBS):
            data = self.client.post_json(
                f"{base}/jobs",
                {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
                headers={"Accept": "application/json"},
            )
            total = data.get("total", 0)
            postings = data.get("jobPostings", [])
            if not postings:
                break
            for p in postings:
                path = p.get("externalPath", "")
                description = None
                date_posted = None
                if path:
                    try:
                        detail = self.client.get_json(f"{base}{path}",
                                                      headers={"Accept": "application/json"})
                        info = detail.get("jobPostingInfo", {})
                        description = html_to_text(info.get("jobDescription", "")) or None
                        date_posted = info.get("startDate")
                    except FetchError:
                        pass  # keep the listing even without a description
                jobs.append(Job(
                    job_id=f"workday:{tenant}:{p.get('bulletFields', [path])[0]}",
                    company=company.company,
                    title=(p.get("title") or "").strip(),
                    location=p.get("locationsText"),
                    job_url=f"https://{host}/{site}{path}" if path else None,
                    description=description,
                    date_posted=date_posted,
                    source="workday",
                    collected_at=now_iso(),
                ))
            offset += PAGE_SIZE
        return jobs
