"""Skill-gap analysis: alias resolution and have/gap splitting."""

from pathlib import Path

from skills_watch.extraction import SkillTaxonomy
from skills_watch.gap import analyse_gap, resolve_skills

TAXONOMY = Path(__file__).resolve().parents[1] / "taxonomy"


def _rows():
    return [
        {"skill": "WordPress", "category": "WordPress", "demand_rate": "28.1",
         "jobs_requiring_skill": "79", "jobs_analysed": "281", "sector": "X",
         "snapshot_date": "2026-08-18"},
        {"skill": "Kubernetes", "category": "Infrastructure", "demand_rate": "25.6",
         "jobs_requiring_skill": "72", "jobs_analysed": "281", "sector": "X",
         "snapshot_date": "2026-08-18"},
        {"skill": "Python", "category": "Programming", "demand_rate": "28.1",
         "jobs_requiring_skill": "79", "jobs_analysed": "281", "sector": "X",
         "snapshot_date": "2026-08-18"},
    ]


def test_resolve_aliases_and_unknowns():
    taxonomy = SkillTaxonomy.load(TAXONOMY)
    have, unknown = resolve_skills(["K8s", "WP", "Underwater Basket Weaving"], taxonomy)
    assert have == {"Kubernetes", "WordPress"}
    assert unknown == ["Underwater Basket Weaving"]


def test_gap_split_and_ordering():
    result = analyse_gap(_rows(), have={"Kubernetes"})
    assert [e["skill"] for e in result["validated"]] == ["Kubernetes"]
    # Gaps sorted by demand rate descending
    assert [e["skill"] for e in result["gaps"]] == ["Python", "WordPress"] or \
           [e["skill"] for e in result["gaps"]] == ["WordPress", "Python"]


def test_gap_with_trends():
    trends = {"Python": {"change_pp": "4.2"}}
    result = analyse_gap(_rows(), have=set(), trends=trends)
    python = next(e for e in result["gaps"] if e["skill"] == "Python")
    assert python["trend_pp"] == 4.2
