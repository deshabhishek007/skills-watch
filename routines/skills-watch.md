# Skills Watch Routine

You are running the recurring Skills Watch analysis. Work from the repository root.
The Python pipeline does all deterministic work; your job is orchestration, quality
review, and the narrative. Do not hand-count jobs or skills yourself.

Default company list: `companies/managed-wordpress-hosting.csv` (override if the
user names another list).

## Phase 1 — Validate

- Read the company CSV. Confirm it parses and note disabled rows.
- If the CLI later warns about malformed rows, report them.

## Phase 2 — Resolve sources

- Companies already carry `source_type`/`source_ref`; leave working ones alone.
- For companies whose last run said `unsupported` with an "embeds ATS" hint, update
  their `source_type`/`source_ref` in the CSV accordingly.
- For `failed` companies, spend at most ~5 minutes checking whether the careers
  URL moved or the ATS changed (WebFetch the careers page). Update the CSV if so;
  otherwise leave the failure to be reported honestly. Never work around
  authentication, CAPTCHAs, or anti-bot measures.

## Phase 3–6 — Collect, clean, extract, analyse (all in Python)

```bash
.venv/bin/python -m skills_watch analyse \
  --companies companies/managed-wordpress-hosting.csv \
  --snapshot
```

If a snapshot for today already exists (re-run), add `--force-snapshot`.

## Phase 7 — Quality check

Read `output/collection_status.csv` and the run summary, then check:

- Any company whose job count moved more than ±50% vs the previous snapshot
  (`output/company_hiring_trends.csv`) — verify against its live careers page
  before treating it as a real signal; it is usually a collector regression.
- Companies with status `failed`/`unsupported` — list them in your summary.
- Jobs with no description (`partial` status) — note the undercount.
- Skim ~10 job titles in `output/jobs.csv` for obviously wrong function/seniority
  classifications; if a pattern is off, fix the taxonomy YAML and re-run.
- Scan a few job descriptions for recurring technologies missing from
  `taxonomy/skills.yml`. Propose additions (with aliases) and apply the
  uncontroversial ones.

## Phase 8 — Report narrative

Open `output/report.md` and replace the placeholder comment under
**Notable Hiring Signals** with 3–6 bullet points. Rules:

- Only claims supported by the CSVs; cite the demand rate or job count.
- Hiring-signal language only: "X appeared in N% of vacancies", never
  "company Y is migrating to X".
- Flag small samples (<10 jobs) whenever you cite a company-level rate.
- When trend data exists, lead with the biggest percentage-point movers.

## Phase 9 — Commit and summarise

```bash
git add -A && git commit -m "Skills Watch snapshot $(date +%F)"
git push
```

Then tell the user: companies requested / succeeded / partial / failed, jobs
collected, unique jobs analysed, skills identified, where the outputs are, and
the 2–3 most notable findings (only if the data supports them).
