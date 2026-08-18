"""Aggregation: demand rates, company/sector summaries, technology matrix, trends.

The headline metric everywhere is the Skill Demand Rate:
    unique jobs requiring skill / total unique jobs analysed * 100
Raw keyword frequency is never used.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .models import Job


def demand_rates(jobs: list[Job]) -> list[tuple[str, int, float]]:
    """[(skill, jobs_requiring_skill, demand_rate_pct)] sorted by demand."""
    if not jobs:
        return []
    counts = Counter(skill for job in jobs for skill in set(job.skills))
    total = len(jobs)
    return sorted(
        ((skill, n, round(n / total * 100, 1)) for skill, n in counts.items()),
        key=lambda x: (-x[1], x[0]),
    )


def distribution(jobs: list[Job], attr: str) -> list[tuple[str, int, float]]:
    """[(value, count, pct)] for a categorical job attribute."""
    if not jobs:
        return []
    counts = Counter(getattr(job, attr) for job in jobs)
    total = len(jobs)
    return sorted(
        ((value or "Unknown", n, round(n / total * 100, 1)) for value, n in counts.items()),
        key=lambda x: (-x[1], x[0]),
    )


@dataclass
class CompanyStats:
    company: str
    sector: str | None
    jobs: list[Job] = field(default_factory=list)

    @property
    def open_jobs(self) -> int:
        return len(self.jobs)

    @property
    def skills(self) -> list[tuple[str, int, float]]:
        return demand_rates(self.jobs)

    @property
    def functions(self) -> list[tuple[str, int, float]]:
        return distribution(self.jobs, "function")

    @property
    def seniority(self) -> list[tuple[str, int, float]]:
        return distribution(self.jobs, "seniority")

    @property
    def remote(self) -> list[tuple[str, int, float]]:
        return distribution(self.jobs, "remote_classification")


def by_company(jobs: list[Job], sectors: dict[str, str | None]) -> list[CompanyStats]:
    grouped: dict[str, list[Job]] = defaultdict(list)
    for job in jobs:
        grouped[job.company].append(job)
    return sorted(
        (CompanyStats(c, sectors.get(c), js) for c, js in grouped.items()),
        key=lambda s: -s.open_jobs,
    )


def by_sector(jobs: list[Job], sectors: dict[str, str | None]) -> dict[str, list[Job]]:
    grouped: dict[str, list[Job]] = defaultdict(list)
    for job in jobs:
        grouped[sectors.get(job.company) or "Unclassified"].append(job)
    return dict(grouped)


def technology_matrix(companies: list[CompanyStats], top_n: int = 12,
                      categories_of_interest: set[str] | None = None,
                      category_of: dict[str, str] | None = None) -> tuple[list[str], list[dict]]:
    """Company × technology demand-rate matrix over the sector's top technical skills."""
    sector_counts: Counter = Counter()
    for cs in companies:
        for skill, n, _ in cs.skills:
            if category_of and categories_of_interest and \
                    category_of.get(skill) not in categories_of_interest:
                continue
            sector_counts[skill] += n
    top_skills = [s for s, _ in sector_counts.most_common(top_n)]
    rows = []
    for cs in companies:
        rates = {skill: rate for skill, _, rate in cs.skills}
        rows.append({"company": cs.company,
                     **{skill: rates.get(skill, 0.0) for skill in top_skills}})
    return top_skills, rows


def skill_trends(current: list[tuple[str, int, float]],
                 previous: list[tuple[str, int, float]]) -> list[dict]:
    """Percentage-point changes in demand rate between two snapshots."""
    prev = {s: (n, rate) for s, n, rate in previous}
    cur = {s: (n, rate) for s, n, rate in current}
    prev_rank = {s: i + 1 for i, (s, _, _) in enumerate(previous)}
    cur_rank = {s: i + 1 for i, (s, _, _) in enumerate(current)}
    out = []
    for skill in sorted(set(prev) | set(cur)):
        cur_rate = cur.get(skill, (0, 0.0))[1]
        prev_rate = prev.get(skill, (0, 0.0))[1]
        out.append({
            "skill": skill,
            "current_demand_rate": cur_rate,
            "previous_demand_rate": prev_rate,
            "change_pp": round(cur_rate - prev_rate, 1),
            "current_rank": cur_rank.get(skill),
            "previous_rank": prev_rank.get(skill),
            "status": ("new" if skill not in prev else
                       "gone" if skill not in cur else "continuing"),
        })
    out.sort(key=lambda r: -abs(r["change_pp"]))
    return out


def hiring_trends(current_jobs: list[Job], previous_job_ids: set[str]) -> dict:
    """New/removed/persistent vacancies between snapshots, by stable job_id."""
    current_ids = {j.job_id for j in current_jobs}
    return {
        "new": sorted(current_ids - previous_job_ids),
        "removed": sorted(previous_job_ids - current_ids),
        "persistent": sorted(current_ids & previous_job_ids),
    }
