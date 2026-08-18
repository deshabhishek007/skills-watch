"""Personal skill-gap analysis: your skills vs what the sector is hiring for.

Deterministic: reads the latest sector_skills.csv (and skill_trends.csv when
present) and splits sector demand into skills you have vs skills to focus on.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from .extraction import SkillTaxonomy


def load_profile(path: str | Path) -> list[str]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    skills = data.get("skills") or []
    return [str(s).strip() for s in skills if str(s).strip()]


def resolve_skills(raw_skills: list[str], taxonomy: SkillTaxonomy) -> tuple[set[str], list[str]]:
    """Map user-written skills (aliases welcome) to canonical taxonomy names.
    Returns (canonical_skills, unrecognised_entries)."""
    have: set[str] = set()
    unknown: list[str] = []
    for raw in raw_skills:
        matched = taxonomy.extract(raw)
        if matched:
            have.update(matched)
        else:
            unknown.append(raw)
    return have, unknown


def analyse_gap(sector_rows: list[dict], have: set[str],
                trends: dict[str, dict] | None = None) -> dict:
    """Split sector demand into validated strengths and gaps, sorted by demand."""
    validated, gaps = [], []
    for r in sector_rows:
        entry = {
            "skill": r["skill"],
            "category": r.get("category") or "",
            "demand_rate": float(r["demand_rate"]),
            "jobs": int(r["jobs_requiring_skill"]),
            "trend_pp": None,
        }
        if trends and r["skill"] in trends:
            entry["trend_pp"] = float(trends[r["skill"]]["change_pp"])
        (validated if r["skill"] in have else gaps).append(entry)
    validated.sort(key=lambda e: -e["demand_rate"])
    gaps.sort(key=lambda e: -e["demand_rate"])
    return {"validated": validated, "gaps": gaps}


def render_markdown(result: dict, sector: str, snapshot_date: str,
                    jobs_analysed: int, have: set[str], unknown: list[str]) -> str:
    def table(entries: list[dict], limit: int) -> str:
        has_trend = any(e["trend_pp"] is not None for e in entries)
        lines = ["| Skill | Category | Demand rate | Jobs |" + (" Trend |" if has_trend else ""),
                 "|---|---|---|---|" + ("---|" if has_trend else "")]
        for e in entries[:limit]:
            row = f"| {e['skill']} | {e['category']} | {e['demand_rate']}% | {e['jobs']} |"
            if has_trend:
                t = e["trend_pp"]
                row += (f" {'+' if t >= 0 else ''}{t} pp |" if t is not None else " — |")
            lines.append(row)
        return "\n".join(lines)

    parts = [
        f"# Your Skill Gap — {sector}\n",
        f"*Against the {snapshot_date} snapshot: {jobs_analysed} analysed jobs. "
        f"Demand rate = share of those jobs mentioning the skill.*\n",
        f"## Skills you have that the market wants ({len(result['validated'])})\n",
        table(result["validated"], 15) if result["validated"] else
        "*None of your listed skills currently appear in this sector's vacancies.*",
        "",
        "## Skills to focus on\n",
        "The highest-demand skills in this sector that aren't on your list:\n",
        table(result["gaps"], 15) if result["gaps"] else
        "*You cover every in-demand skill we found. Nice.*",
        "",
    ]
    if unknown:
        parts.append(f"## Not recognised\n\nThese entries didn't match the taxonomy "
                     f"(add them to `taxonomy/skills.yml` if they're real skills): "
                     f"{', '.join(unknown)}\n")
    parts.append("*Job postings are hiring signals, not a curriculum — use demand "
                 "rates to prioritise, not as a verdict on your career.*")
    return "\n".join(parts) + "\n"


def run_gap(skills_path: str | Path, output_dir: str | Path,
            taxonomy_dir: str | Path) -> tuple[str, dict]:
    """Returns (markdown, result). Raises FileNotFoundError if no sector data."""
    output_dir = Path(output_dir)
    sector_csv = output_dir / "sector_skills.csv"
    if not sector_csv.exists():
        raise FileNotFoundError(
            f"{sector_csv} not found — run `analyse` first to produce sector data")
    with open(sector_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise FileNotFoundError(f"{sector_csv} is empty — the last run collected no jobs")

    trends = None
    trends_csv = output_dir / "skill_trends.csv"
    if trends_csv.exists():
        with open(trends_csv, newline="", encoding="utf-8") as f:
            trends = {r["skill"]: r for r in csv.DictReader(f)}

    taxonomy = SkillTaxonomy.load(taxonomy_dir)
    have, unknown = resolve_skills(load_profile(skills_path), taxonomy)
    # A multi-sector CSV gets one gap report per... no: use the dominant sector
    # (most analysed jobs) and say so.
    sector = max({r["sector"] for r in rows},
                 key=lambda s: max(int(r["jobs_analysed"]) for r in rows if r["sector"] == s))
    sector_rows = [r for r in rows if r["sector"] == sector]
    result = analyse_gap(sector_rows, have, trends)
    md = render_markdown(result, sector, sector_rows[0]["snapshot_date"],
                         int(sector_rows[0]["jobs_analysed"]), have, unknown)
    return md, result
