"""CSV output generation (spec §18)."""

from __future__ import annotations

import csv
from pathlib import Path

from .analysis import CompanyStats, demand_rates, distribution, technology_matrix
from .models import CollectionStatus, Job


def _write(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_all(output_dir: str | Path, snapshot_date: str, jobs: list[Job],
              companies: list[CompanyStats], sector_jobs: dict[str, list[Job]],
              statuses: list[CollectionStatus], category_of: dict[str, str],
              trend_rows: list[dict] | None = None,
              hiring_trend_rows: list[dict] | None = None) -> list[str]:
    out = Path(output_dir)
    written = []

    job_fields = ["job_id", "company", "title", "location", "job_url", "date_posted",
                  "source", "collected_at", "department", "employment_type",
                  "remote_status", "skills", "function", "seniority",
                  "remote_classification", "salary_min", "salary_max", "salary_currency"]
    rows = []
    for j in jobs:
        r = j.to_row()
        r.pop("description", None)  # descriptions are long; jobs.csv stays scannable
        rows.append(r)
    _write(out / "jobs.csv", job_fields, rows)
    written.append("jobs.csv")

    _write(out / "company_summary.csv",
           ["snapshot_date", "company", "sector", "open_jobs", "top_skills",
            "top_function", "remote_share_pct"],
           [{
               "snapshot_date": snapshot_date,
               "company": c.company,
               "sector": c.sector,
               "open_jobs": c.open_jobs,
               "top_skills": "; ".join(f"{s} {r}%" for s, _, r in c.skills[:5]),
               "top_function": c.functions[0][0] if c.functions else None,
               "remote_share_pct": next((r for v, _, r in c.remote if v == "Remote"), 0.0),
           } for c in companies])
    written.append("company_summary.csv")

    _write(out / "company_skills.csv",
           ["snapshot_date", "company", "sector", "skill", "category",
            "jobs_requiring_skill", "jobs_analysed", "demand_rate"],
           [{
               "snapshot_date": snapshot_date, "company": c.company, "sector": c.sector,
               "skill": skill, "category": category_of.get(skill),
               "jobs_requiring_skill": n, "jobs_analysed": c.open_jobs, "demand_rate": rate,
           } for c in companies for skill, n, rate in c.skills])
    written.append("company_skills.csv")

    sector_rows, sector_skill_rows = [], []
    for sector, sjobs in sector_jobs.items():
        active = {j.company for j in sjobs}
        sector_rows.append({
            "snapshot_date": snapshot_date, "sector": sector,
            "companies_hiring": len(active), "total_open_jobs": len(sjobs),
            "jobs_per_company": round(len(sjobs) / len(active), 1) if active else 0,
            "top_skills": "; ".join(f"{s} {r}%" for s, _, r in demand_rates(sjobs)[:10]),
        })
        for skill, n, rate in demand_rates(sjobs):
            sector_skill_rows.append({
                "snapshot_date": snapshot_date, "sector": sector, "skill": skill,
                "category": category_of.get(skill), "jobs_requiring_skill": n,
                "jobs_analysed": len(sjobs), "demand_rate": rate,
            })
    _write(out / "sector_summary.csv",
           ["snapshot_date", "sector", "companies_hiring", "total_open_jobs",
            "jobs_per_company", "top_skills"], sector_rows)
    _write(out / "sector_skills.csv",
           ["snapshot_date", "sector", "skill", "category", "jobs_requiring_skill",
            "jobs_analysed", "demand_rate"], sector_skill_rows)
    written += ["sector_summary.csv", "sector_skills.csv"]

    tech_categories = {"Programming", "WordPress", "Cloud", "Infrastructure", "Data", "AI", "Security"}
    top_skills, matrix_rows = technology_matrix(
        companies, categories_of_interest=tech_categories, category_of=category_of)
    _write(out / "technology_matrix.csv", ["company"] + top_skills, matrix_rows)
    written.append("technology_matrix.csv")

    _write(out / "collection_status.csv",
           ["company", "status", "jobs_found", "source", "detail"],
           [vars(s) for s in statuses])
    written.append("collection_status.csv")

    if trend_rows:
        _write(out / "skill_trends.csv",
               ["skill", "current_demand_rate", "previous_demand_rate", "change_pp",
                "current_rank", "previous_rank", "status"], trend_rows)
        written.append("skill_trends.csv")
    if hiring_trend_rows:
        _write(out / "company_hiring_trends.csv",
               ["company", "current_open_jobs", "previous_open_jobs", "new_jobs",
                "removed_jobs", "persistent_jobs"], hiring_trend_rows)
        written.append("company_hiring_trends.csv")

    return written
