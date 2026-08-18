"""Title normalisation and duplicate removal."""

from __future__ import annotations

import re

from .models import Job


def normalise_title(title: str) -> str:
    """Lowercase, strip req IDs / brackets / punctuation noise for comparison only."""
    t = title.lower()
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)          # parenthetical noise
    t = re.sub(r"[#(]?\b(req|job|id)[\s#:]*\d+\b\)?", " ", t)  # requisition ids
    t = re.sub(r"[^\w\s+#/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def dedup_jobs(jobs: list[Job]) -> tuple[list[Job], int]:
    """One record per unique vacancy. Prefer stable ATS job IDs; fall back to
    (company, normalised title, location). Returns (unique_jobs, removed_count)."""
    seen: set[tuple] = set()
    unique: list[Job] = []
    for job in jobs:
        # ATS IDs are stable and collision-free; generic ones fall through to
        # the fuzzy key so the same vacancy found via two URLs still collapses.
        if job.source != "generic" and job.job_id:
            key: tuple = ("id", job.job_id)
        else:
            key = ("fuzzy", job.company.lower(), normalise_title(job.title),
                   (job.location or "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique, len(jobs) - len(unique)
