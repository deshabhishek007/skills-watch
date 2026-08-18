"""Dedup, demand rates, classification, aggregation and snapshot comparison."""

from pathlib import Path

from skills_watch import analysis
from skills_watch.extraction import RuleClassifier, classify_remote, normalise_location
from skills_watch.normalise import dedup_jobs, normalise_title

from conftest import make_job

TAXONOMY = Path(__file__).resolve().parents[1] / "taxonomy"


def test_dedup_by_ats_id():
    jobs = [make_job(job_id="greenhouse:a:1"), make_job(job_id="greenhouse:a:1"),
            make_job(job_id="greenhouse:a:2")]
    unique, removed = dedup_jobs(jobs)
    assert len(unique) == 2 and removed == 1


def test_dedup_generic_by_title_location():
    jobs = [
        make_job(job_id="generic:Acme:url1", title="Senior PHP Developer (Req #123)", source="generic"),
        make_job(job_id="generic:Acme:url2", title="Senior PHP Developer", source="generic"),
        make_job(job_id="generic:Acme:url3", title="Senior PHP Developer", location="Berlin", source="generic"),
    ]
    unique, removed = dedup_jobs(jobs)
    assert len(unique) == 2 and removed == 1


def test_normalise_title_strips_req_ids():
    assert normalise_title("Senior PHP Developer (Req #123)") == "senior php developer"
    assert normalise_title("  DevOps   Engineer!! ") == "devops engineer"


def test_demand_rate_math():
    jobs = [make_job(job_id=str(i)) for i in range(4)]
    jobs[0].skills = ["Kubernetes", "PHP"]
    jobs[1].skills = ["Kubernetes"]
    jobs[2].skills = ["PHP"]
    jobs[3].skills = []
    rates = dict((s, (n, r)) for s, n, r in analysis.demand_rates(jobs))
    assert rates["Kubernetes"] == (2, 50.0)
    assert rates["PHP"] == (2, 50.0)


def test_company_and_sector_aggregation():
    jobs = ([make_job(job_id=f"a{i}", company="Acme") for i in range(3)] +
            [make_job(job_id=f"g{i}", company="Globex") for i in range(2)])
    sectors = {"Acme": "Hosting", "Globex": "Hosting"}
    stats = analysis.by_company(jobs, sectors)
    assert [(s.company, s.open_jobs) for s in stats] == [("Acme", 3), ("Globex", 2)]
    grouped = analysis.by_sector(jobs, sectors)
    assert len(grouped["Hosting"]) == 5


def test_function_classification():
    clf = RuleClassifier.load(TAXONOMY / "functions.yml", "functions", default="Other")
    assert clf.classify("Site Reliability Engineer") == "Infrastructure / SRE"
    assert clf.classify("Senior Software Engineer") == "Engineering"
    assert clf.classify("Customer Support Specialist") == "Customer Support"
    assert clf.classify("Happiness Engineer") == "Customer Support"  # Automattic's support role
    assert clf.classify("Growth Marketing Manager") == "Marketing"
    assert clf.classify("Llama Groomer") == "Other"


def test_seniority_classification():
    clf = RuleClassifier.load(TAXONOMY / "seniority.yml", "levels")
    assert clf.classify("Senior PHP Developer") == "Senior"
    assert clf.classify("Engineering Manager") == "Manager"
    assert clf.classify("VP of Sales") == "VP"
    assert clf.classify("Software Engineering Intern") == "Intern"
    assert clf.classify("PHP Developer") == "Unknown"


def test_remote_classification():
    assert classify_remote("Remote — Worldwide", "Engineer", None) == "Remote"
    assert classify_remote("Austin, TX (Hybrid)", "Engineer", None) == "Hybrid"
    assert classify_remote("Sofia, Bulgaria", "Engineer", None) == "On-site"
    assert classify_remote(None, "Engineer", None) == "Unknown"
    assert classify_remote(None, "Engineer", None, ats_remote_status="Remote") == "Remote"


def test_location_normalisation():
    assert normalise_location("Remote — Anywhere") == "Worldwide"
    assert normalise_location("Bengaluru, India") == "India"
    assert normalise_location("Sofia, Bulgaria") == "Europe"
    assert normalise_location(None) == "Unknown"


def test_skill_trends():
    current = [("Kubernetes", 20, 16.8), ("PHP", 30, 25.0), ("Rust", 5, 4.2)]
    previous = [("Kubernetes", 12, 12.1), ("PHP", 31, 26.0), ("Perl", 3, 2.5)]
    trends = {r["skill"]: r for r in analysis.skill_trends(current, previous)}
    assert trends["Kubernetes"]["change_pp"] == 4.7
    assert trends["Rust"]["status"] == "new"
    assert trends["Perl"]["status"] == "gone"


def test_hiring_trends():
    current = [make_job(job_id="a"), make_job(job_id="b")]
    t = analysis.hiring_trends(current, previous_job_ids={"b", "c"})
    assert t["new"] == ["a"] and t["removed"] == ["c"] and t["persistent"] == ["b"]
