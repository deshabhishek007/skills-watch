import pytest

from skills_watch.models import Job


def make_job(job_id="j1", company="Acme Hosting", title="Software Engineer",
             location="Remote", description="", source="greenhouse", **kw) -> Job:
    return Job(job_id=job_id, company=company, title=title, location=location,
               job_url=None, description=description, date_posted=None,
               source=source, collected_at="2026-08-18T00:00:00Z", **kw)


@pytest.fixture
def taxonomy():
    from pathlib import Path
    from skills_watch.extraction import SkillTaxonomy
    return SkillTaxonomy.load(Path(__file__).resolve().parents[1] / "taxonomy")
