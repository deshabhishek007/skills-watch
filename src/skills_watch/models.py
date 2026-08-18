"""Common data models: the job schema shared by all collectors, and company config."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Job:
    """One unique vacancy. Fields the source doesn't provide stay None — never fabricated."""

    job_id: str
    company: str
    title: str
    location: str | None
    job_url: str | None
    description: str | None
    date_posted: str | None
    source: str
    collected_at: str

    department: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None

    # Filled in by extraction
    skills: list[str] = field(default_factory=list)
    function: str = "Unknown"
    seniority: str = "Unknown"
    remote_classification: str = "Unknown"

    def to_row(self) -> dict:
        d = asdict(self)
        d["skills"] = "; ".join(self.skills)
        return d


@dataclass
class CompanyConfig:
    company: str
    website: str | None = None
    careers_url: str | None = None
    sector: str | None = None
    enabled: bool = True
    notes: str | None = None
    # Collector hints, stored so future runs skip rediscovery
    source_type: str | None = None  # greenhouse | workday | workable | bamboohr | generic
    source_ref: str | None = None   # ATS board token / tenant id / listing URL


@dataclass
class CollectionStatus:
    company: str
    status: str  # success | partial | failed | no_open_jobs | unsupported | disabled
    jobs_found: int = 0
    detail: str | None = None
    source: str | None = None


def load_companies(path: str | Path) -> tuple[list[CompanyConfig], list[str]]:
    """Load company CSV. Only `company` is required. Returns (companies, problems)."""
    companies: list[CompanyConfig] = []
    problems: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "company" not in reader.fieldnames:
            return [], [f"{path}: missing required 'company' column"]
        for i, row in enumerate(reader, start=2):
            name = (row.get("company") or "").strip()
            if not name:
                problems.append(f"row {i}: empty company name — skipped")
                continue
            enabled = (row.get("enabled") or "true").strip().lower() not in ("false", "0", "no")
            companies.append(
                CompanyConfig(
                    company=name,
                    website=(row.get("website") or "").strip() or None,
                    careers_url=(row.get("careers_url") or "").strip() or None,
                    sector=(row.get("sector") or "").strip() or None,
                    enabled=enabled,
                    notes=(row.get("notes") or "").strip() or None,
                    source_type=(row.get("source_type") or "").strip() or None,
                    source_ref=(row.get("source_ref") or "").strip() or None,
                )
            )
    return companies, problems
