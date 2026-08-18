# Skills Watch

> Turn public company job openings into structured hiring, skill and technology intelligence.

Point it at a CSV of companies — WordPress hosts, banks, SaaS vendors, any
competitive set — and it collects their open jobs from official careers sources,
extracts and normalises skills, and produces CSV datasets plus a Markdown
research report. Dated snapshots make every run comparable with the last, so you
can watch skill demand shift in your industry over time.

The first published dataset here tracks the **Managed WordPress Hosting**
industry: see [`output/report.md`](output/report.md) and the history in
[`snapshots/`](snapshots/).

## Quick start

```bash
git clone https://github.com/deshabhishek007/skills-watch && cd skills-watch
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/python -m skills_watch analyse \
  --companies companies/managed-wordpress-hosting.csv \
  --snapshot
```

Outputs land in `output/` (see below); `--snapshot` also archives them to
`snapshots/<date>/`.

Useful flags: `--company X` / `--sector Y` (restrict the run),
`--snapshot-date YYYY-MM-DD`, `--force-snapshot` (same-day re-run), `--no-report`.

## Watch your own industry

1. Copy `companies/example.csv` and fill in your companies. Only `company` is
   required:

   ```csv
   company,website,careers_url,sector,enabled,notes,source_type,source_ref
   Acme Corp,https://acme.com,https://acme.com/careers,SaaS,true,,greenhouse,acmecorp
   ```

2. Set `source_type`/`source_ref` where you know the ATS (see table below).
   Everything else falls back to the `generic` HTML collector, which also
   detects embedded ATS boards and tells you what to configure.
3. Run the command above with your CSV.
4. Optionally schedule it: this repo includes a Claude Code routine
   (`routines/skills-watch.md`) that runs the pipeline, quality-checks the
   results, writes the report narrative, and commits the snapshot. Schedule it
   with Claude Code's scheduled agents (`/schedule` → point it at the routine),
   cron, or any runner you like — the pipeline itself needs no LLM.

## Supported collectors

| `source_type` | `source_ref` | Source |
|---|---|---|
| `greenhouse` | board token | `boards-api.greenhouse.io/v1/boards/{token}/jobs` |
| `lever` | account | `api.lever.co/v0/postings/{account}` |
| `workday` | `host\|site`, e.g. `acme.wd1.myworkdayjobs.com\|External` | Workday CXS JSON API |
| `workable` | account | `apply.workable.com/api/v3/accounts/{account}` |
| `bamboohr` | subdomain | `{sub}.bamboohr.com/careers/list` |
| `generic` | — | best-effort HTML scrape of `careers_url` |

Adding an ATS = one small class in `src/skills_watch/collectors/` with the
`@register` decorator returning the common `Job` schema. Contributions welcome.

## Outputs

| File | Contents |
|---|---|
| `jobs.csv` | every unique vacancy with extracted skills, function, seniority, remote status |
| `company_summary.csv`, `company_skills.csv` | per-company hiring stats and skill demand rates |
| `sector_summary.csv`, `sector_skills.csv` | sector-level aggregation |
| `technology_matrix.csv` | company × technology demand-rate matrix |
| `collection_status.csv` | per-company collection outcome — failures are never counted as zero hiring |
| `skill_trends.csv`, `company_hiring_trends.csv` | changes vs the previous snapshot (when one exists) |
| `report.md` | the human-readable research report |

## Skill methodology

The headline metric is the **skill demand rate**:

```
unique jobs mentioning skill / total unique jobs analysed × 100
```

Skills are matched against a curated taxonomy (`taxonomy/skills.yml`) with
word-boundary matching and alias normalisation (`taxonomy/skill_aliases.yml` —
"K8s" and "Kubernetes" are one skill). A job mentioning a skill ten times counts
once. Raw keyword frequency is never used. To tune extraction for your industry,
edit the YAML files — no code changes needed.

## Historical snapshots

Every `--snapshot` run archives the outputs to `snapshots/<date>/`, which is
committed to git and never overwritten. When at least one prior snapshot exists,
the next run automatically reports new/removed jobs per company and
percentage-point changes in skill demand.

## Limitations

- Job postings are **hiring signals**, not proof of a company's internal stack
  or strategy.
- The `generic` collector is best-effort; JavaScript-rendered careers sites
  come back `failed`/`unsupported` and are excluded from the stats (and say so).
- Employers sometimes post one listing for several openings, or several
  listings for one opening; stable ATS IDs limit but don't eliminate this.
- Diversified companies (a registrar that also does hosting) contribute their
  whole hiring pipeline, not just the segment you're watching.

## Ethics

Official careers sources only, ~1.5s between requests, day-scoped response
cache, honest User-Agent, no authentication or anti-bot circumvention, no
applicant or employee personal data — vacancy text only.
