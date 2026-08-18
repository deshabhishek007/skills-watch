"""Markdown research report (spec §19). Sections appear only when the data
supports them; language stays at the level of hiring signals, never claims
about internal strategy."""

from __future__ import annotations

from .analysis import CompanyStats, demand_rates, distribution
from .extraction.classify import normalise_location
from .models import CollectionStatus, Job

SMALL_SAMPLE = 10


def _table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def generate(snapshot_date: str, sector_label: str, jobs: list[Job],
             companies: list[CompanyStats], statuses: list[CollectionStatus],
             category_of: dict[str, str], trend_rows: list[dict] | None = None,
             previous_date: str | None = None) -> str:
    total = len(jobs)
    ok = [s for s in statuses if s.status in ("success", "partial")]
    parts: list[str] = []
    add = parts.append

    add(f"# Skills Watch: {sector_label}\n")
    add(f"*Snapshot date: {snapshot_date} · {total} unique open jobs across "
        f"{len([c for c in companies if c.open_jobs])} companies*\n")

    add("## Methodology\n")
    add(f"Public job postings were collected from official careers sources for "
        f"{len(statuses)} companies. Postings were deduplicated (stable ATS job IDs "
        f"where available), and skills were matched against a curated taxonomy with "
        f"alias normalisation. The headline metric is the **skill demand rate**: the "
        f"percentage of unique analysed jobs that mention a skill — a job mentioning "
        f"a skill many times still counts once. Job postings are hiring signals; they "
        f"do not prove what technology a company runs in production, and collection "
        f"failures are reported separately rather than counted as zero hiring.\n")

    add("## Collection Status\n")
    add(_table(["Company", "Status", "Jobs", "Source"],
               [[s.company, s.status, s.jobs_found, s.source or "—"] for s in statuses]))
    add("")
    failed = [s for s in statuses if s.status in ("failed", "unsupported")]
    if failed:
        add(f"*{len(failed)} of {len(statuses)} companies could not be collected; "
            f"their hiring is **not** included in the numbers below.*\n")

    if not total:
        add("## No jobs collected\n\nNo analysable jobs were collected in this run.")
        return "\n".join(parts)

    add("## Top Skills\n")
    add("Share of all analysed jobs that mention each skill:\n")
    add(_table(["Skill", "Category", "Jobs", "Demand rate"],
               [[s, category_of.get(s, "—"), n, f"{r}%"]
                for s, n, r in demand_rates(jobs)[:25]]))
    add("")

    tech_categories = {"Programming", "WordPress", "Cloud", "Infrastructure", "Data", "AI", "Security"}
    tech = [(s, n, r) for s, n, r in demand_rates(jobs)
            if category_of.get(s) in tech_categories]
    if tech:
        add("## Top Technologies\n")
        add(_table(["Technology", "Category", "Jobs", "Demand rate"],
                   [[s, category_of.get(s), n, f"{r}%"] for s, n, r in tech[:20]]))
        add("")

    add("## Hiring by Company\n")
    add(_table(["Company", "Open jobs", "Top function", "Top skills"],
               [[c.company, c.open_jobs,
                 c.functions[0][0] if c.functions else "—",
                 ", ".join(s for s, _, _ in c.skills[:5]) or "—"]
                for c in companies if c.open_jobs]))
    add("")

    add("## Skills by Company\n")
    for c in companies:
        if not c.open_jobs:
            continue
        caveat = (f" ⚠️ *small sample ({c.open_jobs} jobs) — treat rates as indicative only*"
                  if c.open_jobs < SMALL_SAMPLE else "")
        add(f"### {c.company} — {c.open_jobs} jobs{caveat}\n")
        top = c.skills[:8]
        if top:
            add(_table(["Skill", "Jobs", "Demand rate"],
                       [[s, n, f"{r}%"] for s, n, r in top]))
        else:
            add("*No taxonomy skills detected in this company's postings.*")
        add("")

    add("## Job Function Analysis\n")
    add(_table(["Function", "Jobs", "Share"],
               [[f, n, f"{r}%"] for f, n, r in distribution(jobs, "function")]))
    add("")

    add("## Seniority Mix\n")
    add(_table(["Level", "Jobs", "Share"],
               [[s, n, f"{r}%"] for s, n, r in distribution(jobs, "seniority")]))
    add("")

    add("## Remote Work Analysis\n")
    add(_table(["Arrangement", "Jobs", "Share"],
               [[v, n, f"{r}%"] for v, n, r in distribution(jobs, "remote_classification")]))
    add("")

    from collections import Counter
    geo = Counter(normalise_location(j.location) for j in jobs)
    add("## Location Analysis\n")
    add("Coarse geography inferred from raw location text (raw text preserved in `jobs.csv`):\n")
    add(_table(["Region", "Jobs", "Share"],
               [[g, n, f"{round(n / total * 100, 1)}%"]
                for g, n in geo.most_common()]))
    add("")

    if trend_rows and previous_date:
        add(f"## Changes Since Previous Snapshot ({previous_date})\n")
        movers = [r for r in trend_rows if r["status"] == "continuing"][:10]
        if movers:
            add(_table(["Skill", "Now", "Then", "Change"],
                       [[r["skill"], f"{r['current_demand_rate']}%",
                         f"{r['previous_demand_rate']}%",
                         f"{'+' if r['change_pp'] >= 0 else ''}{r['change_pp']} pp"]
                        for r in movers]))
        new = [r["skill"] for r in trend_rows if r["status"] == "new"]
        gone = [r["skill"] for r in trend_rows if r["status"] == "gone"]
        if new:
            add(f"\n**Newly appearing skills:** {', '.join(new[:15])}")
        if gone:
            add(f"\n**No longer appearing:** {', '.join(gone[:15])}")
        add("")

    add("## Notable Hiring Signals\n")
    add("<!-- narrative: written by the analyst/routine after reviewing the data -->\n")

    add("## Data Quality and Limitations\n")
    no_desc = sum(1 for j in jobs if not j.description)
    add(f"- {len(ok)} of {len(statuses)} companies collected successfully.")
    if no_desc:
        add(f"- {no_desc} of {total} jobs had no retrievable description; their skills "
            f"come from titles only and are undercounted.")
    add("- Demand rates measure mentions in job postings, not production usage.")
    add("- Companies publishing one listing for several openings (or several listings "
        "for one opening) skew counts; stable ATS IDs limit but don't eliminate this.")
    add("- Large diversified companies (e.g. GoDaddy, DigitalOcean, Newfold) hire far "
        "beyond managed WordPress hosting; their postings reflect the whole business.")

    return "\n".join(parts) + "\n"
