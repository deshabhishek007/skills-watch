"""BambooHR public careers API: https://{sub}.bamboohr.com/careers/list"""

from __future__ import annotations

from ..models import CompanyConfig, Job
from .base import Collector, FetchError, now_iso, register
from .greenhouse import html_to_text


@register
class BambooHRCollector(Collector):
    name = "bamboohr"

    def collect(self, company: CompanyConfig) -> list[Job]:
        sub = company.source_ref
        if not sub:
            raise FetchError("bamboohr collector needs source_ref (subdomain)")
        base = f"https://{sub}.bamboohr.com/careers"
        data = self.client.get_json(f"{base}/list", headers={"Accept": "application/json"})
        jobs: list[Job] = []
        for j in data.get("result", []):
            job_id = j.get("id")
            description = None
            try:
                detail = self.client.get_json(f"{base}/{job_id}/detail",
                                              headers={"Accept": "application/json"})
                desc_html = (detail.get("result") or {}).get("jobOpening", {}).get("description", "")
                description = html_to_text(desc_html) or None
            except FetchError:
                pass
            loc = j.get("location") or {}
            location = ", ".join(x for x in [loc.get("city"), loc.get("state")] if x) or None
            is_remote = str(j.get("isRemote", "")).lower() in ("1", "true", "yes")
            jobs.append(Job(
                job_id=f"bamboohr:{sub}:{job_id}",
                company=company.company,
                title=(j.get("jobOpeningName") or "").strip(),
                location=location,
                job_url=f"{base}/{job_id}",
                description=description,
                date_posted=None,
                source="bamboohr",
                collected_at=now_iso(),
                department=j.get("departmentLabel"),
                employment_type=j.get("employmentStatusLabel"),
                remote_status="Remote" if is_remote else None,
            ))
        return jobs
