# skills-watch

Turn public company job openings into structured hiring, skill and technology
intelligence. Python does everything deterministic; Claude orchestrates runs via
`routines/skills-watch.md` and writes the report narrative.

## Commands

```bash
.venv/bin/python -m pytest -q                 # offline, fixture-based tests
.venv/bin/python -m skills_watch analyse \
  --companies companies/managed-wordpress-hosting.csv --snapshot
```

## Architecture

- `src/skills_watch/collectors/` — one adapter per ATS (greenhouse, workday,
  lever, workable, bamboohr) + `generic` HTML fallback. All share the
  rate-limited, day-cached `HttpClient` in `base.py`. Register new collectors
  with the `@register` decorator; `source_type` in the company CSV selects them.
- `taxonomy/*.yml` — skills (categorised), aliases, function rules, seniority
  rules. Editing YAML is the normal way to improve extraction; code changes are
  rarely needed.
- `analysis.py` — the headline metric everywhere is **skill demand rate** =
  unique jobs mentioning skill / unique jobs analysed. Never raw keyword counts.
- `snapshots/YYYY-MM-DD/` — committed history; never overwritten (only
  `--force-snapshot` for a same-day re-run). Trends compare against the latest
  prior snapshot.

## Rules

- Missing data stays `null`/`Unknown` — never fabricated, never forced.
- Collection failure ≠ zero hiring: failures go to `collection_status.csv`.
- Report language: hiring signals only; job ads don't prove production usage.
- Politeness: official sources, ~1.5s between requests, day-scoped cache, no
  auth/CAPTCHA circumvention. Uncollectable sources are marked `unsupported`.
