"""CLI: python -m skills_watch analyse --companies companies/foo.csv [--output output/]"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import analysis, charts, outputs, report, snapshots
from .collectors import get_collector
from .collectors.base import FetchError, HttpClient
from .collectors.generic import EmbeddedATSFound
from .extraction import RuleClassifier, SkillTaxonomy, classify_remote
from .models import CollectionStatus, load_companies
from .normalise import dedup_jobs

ROOT = Path(__file__).resolve().parents[2]


def analyse(args: argparse.Namespace) -> int:
    snapshot_date = args.snapshot_date or date.today().isoformat()
    output_dir = Path(args.output)
    taxonomy_dir = Path(args.taxonomy)
    snapshots_dir = Path(args.snapshots)

    companies, problems = load_companies(args.companies)
    for p in problems:
        print(f"warning: {p}", file=sys.stderr)
    if not companies:
        print("error: no valid companies in input", file=sys.stderr)
        return 1
    if args.company:
        companies = [c for c in companies if c.company.lower() == args.company.lower()]
    if args.sector:
        companies = [c for c in companies if (c.sector or "").lower() == args.sector.lower()]

    taxonomy = SkillTaxonomy.load(taxonomy_dir)
    fn_classifier = RuleClassifier.load(taxonomy_dir / "functions.yml", "functions", default="Other")
    sen_classifier = RuleClassifier.load(taxonomy_dir / "seniority.yml", "levels")

    client = HttpClient(cache_dir=output_dir / "cache")
    all_jobs, statuses = [], []
    for cfg in companies:
        if not cfg.enabled:
            statuses.append(CollectionStatus(cfg.company, "disabled"))
            continue
        source = cfg.source_type or "generic"
        collector = get_collector(source, client)
        if collector is None:
            statuses.append(CollectionStatus(cfg.company, "unsupported",
                                             detail=f"unknown source_type '{source}'"))
            continue
        print(f"collecting {cfg.company} via {source}...", file=sys.stderr)
        try:
            jobs = collector.collect(cfg)
        except EmbeddedATSFound as e:
            statuses.append(CollectionStatus(cfg.company, "unsupported", source=source,
                                             detail=str(e)))
            continue
        except FetchError as e:
            statuses.append(CollectionStatus(cfg.company, "failed", source=source,
                                             detail=str(e)))
            continue
        except Exception as e:  # a collector bug must not kill the whole run
            statuses.append(CollectionStatus(cfg.company, "failed", source=source,
                                             detail=f"collector error: {type(e).__name__}: {e}"))
            continue
        if not jobs:
            statuses.append(CollectionStatus(cfg.company, "no_open_jobs", source=source))
            continue
        missing_desc = sum(1 for j in jobs if not j.description)
        status = "partial" if missing_desc > len(jobs) * 0.5 else "success"
        statuses.append(CollectionStatus(cfg.company, status, jobs_found=len(jobs),
                                         source=source,
                                         detail=f"{missing_desc} without description" if missing_desc else None))
        all_jobs.extend(jobs)

    unique_jobs, removed = dedup_jobs(all_jobs)

    def is_self_brand(skill: str, company_name: str) -> bool:
        # A company's own brand in its postings is boilerplate, not a skill signal
        # (every DigitalOcean job "mentions" DigitalOcean).
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        return norm(skill) == norm(company_name)

    for job in unique_jobs:
        text = f"{job.title}\n{job.description or ''}"
        job.skills = [s for s in taxonomy.extract(text)
                      if not is_self_brand(s, job.company)]
        job.function = fn_classifier.classify(job.title, job.department)
        job.seniority = sen_classifier.classify(job.title)
        job.remote_classification = classify_remote(
            job.location, job.title, job.description, job.remote_status)

    sectors = {c.company: c.sector for c in companies}
    company_stats = analysis.by_company(unique_jobs, sectors)
    sector_jobs = analysis.by_sector(unique_jobs, sectors)

    # Trends against the most recent prior snapshot
    trend_rows = hiring_trend_rows = None
    prev_date = snapshots.previous_snapshot(snapshots_dir, snapshot_date)
    if prev_date:
        prev_skills = snapshots.load_snapshot_csv(snapshots_dir, prev_date, "sector_skills.csv")
        if prev_skills:
            previous = [(r["skill"], int(r["jobs_requiring_skill"]), float(r["demand_rate"]))
                        for r in prev_skills]
            trend_rows = analysis.skill_trends(analysis.demand_rates(unique_jobs), previous)
        prev_jobs = snapshots.load_snapshot_csv(snapshots_dir, prev_date, "jobs.csv")
        if prev_jobs:
            prev_by_company: dict[str, set[str]] = {}
            for r in prev_jobs:
                prev_by_company.setdefault(r["company"], set()).add(r["job_id"])
            hiring_trend_rows = []
            for cs in company_stats:
                prev_ids = prev_by_company.get(cs.company, set())
                t = analysis.hiring_trends(cs.jobs, prev_ids)
                hiring_trend_rows.append({
                    "company": cs.company, "current_open_jobs": cs.open_jobs,
                    "previous_open_jobs": len(prev_ids), "new_jobs": len(t["new"]),
                    "removed_jobs": len(t["removed"]), "persistent_jobs": len(t["persistent"]),
                })

    written = outputs.write_all(output_dir, snapshot_date, unique_jobs, company_stats,
                                sector_jobs, statuses, taxonomy.category_of,
                                trend_rows, hiring_trend_rows)

    # Chart history: prior snapshots + this run
    skill_history: list[tuple[str, dict[str, float]]] = []
    company_history: list[tuple[str, dict[str, int]]] = []
    for d in snapshots.list_snapshots(snapshots_dir):
        if d >= snapshot_date:
            continue
        srows = snapshots.load_snapshot_csv(snapshots_dir, d, "sector_skills.csv")
        crows = snapshots.load_snapshot_csv(snapshots_dir, d, "company_summary.csv")
        if srows:
            skill_history.append((d, {r["skill"]: float(r["demand_rate"]) for r in srows}))
        if crows:
            company_history.append((d, {r["company"]: int(r["open_jobs"]) for r in crows}))
    current_rates = analysis.demand_rates(unique_jobs)
    skill_history.append((snapshot_date, {s: r for s, _, r in current_rates}))
    company_history.append((snapshot_date, {c.company: c.open_jobs for c in company_stats}))
    chart_paths = charts.write_charts(output_dir, current_rates, len(unique_jobs),
                                      snapshot_date, skill_history, company_history)
    written += chart_paths

    if not args.no_report:
        sector_label = args.sector or next(
            (s for s in {c.sector for c in companies} if s), "Custom Company Set")
        md = report.generate(snapshot_date, sector_label, unique_jobs, company_stats,
                             statuses, taxonomy.category_of, trend_rows, prev_date,
                             chart_paths)
        (output_dir / "report.md").write_text(md, encoding="utf-8")
        written.append("report.md")

    if args.snapshot:
        snapshots.save_snapshot(output_dir, snapshots_dir, snapshot_date,
                                force=args.force_snapshot)

    # Run summary (spec §25 phase 9)
    counts = Counter(s.status for s in statuses)
    print(f"\ncompanies requested:    {len(companies)}")
    for status in ("success", "partial", "failed", "no_open_jobs", "unsupported", "disabled"):
        if counts.get(status):
            print(f"  {status:<21} {counts[status]}")
    print(f"jobs collected:         {len(all_jobs)}")
    print(f"duplicates removed:     {removed}")
    print(f"unique jobs analysed:   {len(unique_jobs)}")
    print(f"skills identified:      {len({s for j in unique_jobs for s in j.skills})}")
    print(f"outputs:                {output_dir}/ ({', '.join(written)})")
    if args.snapshot:
        print(f"snapshot saved:         {snapshots_dir}/{snapshot_date}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills_watch")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyse", help="collect and analyse job postings")
    a.add_argument("--companies", required=True, help="company CSV path")
    a.add_argument("--output", default=str(ROOT / "output"))
    a.add_argument("--taxonomy", default=str(ROOT / "taxonomy"))
    a.add_argument("--snapshots", default=str(ROOT / "snapshots"))
    a.add_argument("--company", help="restrict to one company")
    a.add_argument("--sector", help="restrict to one sector")
    a.add_argument("--snapshot-date", help="YYYY-MM-DD (default: today)")
    a.add_argument("--snapshot", action="store_true", help="save a dated snapshot")
    a.add_argument("--force-snapshot", action="store_true",
                   help="replace an existing snapshot for the same date")
    a.add_argument("--no-report", action="store_true")
    a.set_defaults(func=analyse)

    g = sub.add_parser("gap", help="compare your skills against the sector's demand")
    g.add_argument("--skills", required=True, help="YAML file with a `skills:` list")
    g.add_argument("--output", default=str(ROOT / "output"))
    g.add_argument("--taxonomy", default=str(ROOT / "taxonomy"))
    g.set_defaults(func=gap_cmd)

    args = parser.parse_args(argv)
    return args.func(args)


def gap_cmd(args: argparse.Namespace) -> int:
    from .gap import run_gap
    try:
        md, result = run_gap(args.skills, args.output, args.taxonomy)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    out = Path(args.output) / "skill_gap.md"
    out.write_text(md, encoding="utf-8")
    top_gaps = ", ".join(e["skill"] for e in result["gaps"][:5])
    print(f"skills validated by market demand: {len(result['validated'])}")
    print(f"gap skills identified:            {len(result['gaps'])}")
    print(f"top gaps by demand:               {top_gaps}")
    print(f"report:                           {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
