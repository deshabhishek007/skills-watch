"""Polished SVG charts for the report, generated with no plotting dependency.

Committed SVGs render natively in GitHub markdown. The palette is a validated
colorblind-safe categorical set (adjacent-pair CVD ΔE ≥ 8); series identity is
never carried by color alone — every line ends in a direct label and the report's
tables are the data view. Charts commit to a single light look because GitHub
renders them inside <img>, where theme toggles can't reach.
"""

from __future__ import annotations

import html
from pathlib import Path

# Validated categorical slots, fixed order — never cycled, never re-ordered.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BORDER = "rgba(11,11,11,0.10)"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

CHAR_W = 6.6  # crude width estimate for 12px system sans


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _frame(width: int, height: int, title: str, subtitle: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family='{FONT}'>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8"
        fill="{SURFACE}" stroke="{BORDER}"/>
  <text x="20" y="30" font-size="15" font-weight="600" fill="{INK}">{_esc(title)}</text>
  <text x="20" y="48" font-size="12" fill="{INK_2}">{_esc(subtitle)}</text>
{body}</svg>
"""


def top_skills_bar(skills: list[tuple[str, int, float]], jobs_analysed: int,
                   snapshot_date: str, top_n: int = 10) -> str:
    """Horizontal bar chart of current demand rates. Single measure → single hue."""
    rows = skills[:top_n]
    if not rows:
        return ""
    width, row_h, top_pad = 720, 30, 64
    label_w = max(int(len(s) * CHAR_W) for s, _, _ in rows) + 28
    chart_w = width - label_w - 70
    height = top_pad + row_h * len(rows) + 16
    max_rate = max(r for _, _, r in rows)
    parts = []
    for i, (skill, n, rate) in enumerate(rows):
        y = top_pad + i * row_h
        bar_w = max(4.0, rate / max_rate * chart_w)
        parts.append(
            f'  <text x="{label_w - 8}" y="{y + 15}" font-size="12" fill="{INK_2}" '
            f'text-anchor="end">{_esc(skill)}</text>\n'
            # 12px-thin bar, 4px rounded data end anchored on a square baseline edge
            f'  <path d="M{label_w},{y + 4} h{bar_w - 4:.1f} a4,4 0 0 1 4,4 v4 '
            f'a4,4 0 0 1 -4,4 h-{bar_w - 4:.1f} z" fill="{SERIES[0]}"/>\n'
            f'  <text x="{label_w + bar_w + 6:.1f}" y="{y + 15}" font-size="12" '
            f'fill="{INK}" font-weight="600">{rate}%</text>\n'
        )
    parts.append(f'  <line x1="{label_w}" y1="{top_pad - 4}" x2="{label_w}" '
                 f'y2="{top_pad + row_h * len(rows)}" stroke="{BASELINE}"/>\n')
    return _frame(width, height, "Top skills by demand rate",
                  f"Share of {jobs_analysed} unique open jobs mentioning each skill · "
                  f"snapshot {snapshot_date}", "".join(parts))


def _line_chart(title: str, subtitle: str, dates: list[str],
                series: list[tuple[str, list[float | None]]], unit: str) -> str:
    """Multi-series line chart over snapshot dates with direct end labels."""
    if len(dates) < 2 or not series:
        return ""
    width, height = 720, 360
    pad_l, pad_r, pad_t, pad_b = 52, 150, 64, 36
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    all_vals = [v for _, vals in series for v in vals if v is not None]
    v_max = max(all_vals) * 1.15 or 1
    xs = [pad_l + i * plot_w / (len(dates) - 1) for i in range(len(dates))]

    def y_of(v: float) -> float:
        return pad_t + plot_h - (v / v_max) * plot_h

    parts = []
    ticks = 4
    for t in range(ticks + 1):
        v = v_max * t / ticks
        y = y_of(v)
        parts.append(f'  <line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" '
                     f'y2="{y:.1f}" stroke="{GRID}"/>\n'
                     f'  <text x="{pad_l - 8}" y="{y + 4:.1f}" font-size="11" '
                     f'fill="{MUTED}" text-anchor="end">{v:.0f}{unit}</text>\n')
    for i, d in enumerate(dates):
        parts.append(f'  <text x="{xs[i]:.1f}" y="{height - 14}" font-size="11" '
                     f'fill="{MUTED}" text-anchor="middle">{_esc(d[5:])}</text>\n')
    parts.append(f'  <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" '
                 f'y2="{pad_t + plot_h}" stroke="{BASELINE}"/>\n')

    # Spread end labels vertically so they never collide
    ends = sorted(range(len(series)),
                  key=lambda i: next((v for v in reversed(series[i][1]) if v is not None), 0),
                  reverse=True)
    label_y: dict[int, float] = {}
    prev = pad_t - 20
    for idx in ends:
        last = next((v for v in reversed(series[idx][1]) if v is not None), 0)
        y = max(y_of(last), prev + 16)
        label_y[idx] = y
        prev = y

    for idx, (name, vals) in enumerate(series):
        color = SERIES[idx % len(SERIES)]
        pts = [(xs[i], y_of(v)) for i, v in enumerate(vals) if v is not None]
        if not pts:
            continue
        path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'  <path d="{path}" fill="none" stroke="{color}" '
                     f'stroke-width="2" stroke-linejoin="round"/>\n')
        for x, y in pts:
            # 8px marker with a 2px surface ring so overlaps stay separable
            parts.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" '
                         f'stroke="{SURFACE}" stroke-width="2"/>\n')
        lx, ly = pts[-1][0] + 10, label_y[idx] + 4
        last_val = next(v for v in reversed(vals) if v is not None)
        parts.append(f'  <circle cx="{lx}" cy="{ly - 4:.1f}" r="4" fill="{color}"/>\n'
                     f'  <text x="{lx + 8}" y="{ly:.1f}" font-size="12" fill="{INK_2}">'
                     f'{_esc(name)} <tspan font-weight="600" fill="{INK}">'
                     f'{last_val:g}{unit}</tspan></text>\n')
    return _frame(width, height, title, subtitle, "".join(parts))


def demand_trend_chart(history: list[tuple[str, dict[str, float]]], top_n: int = 6) -> str:
    """history: [(snapshot_date, {skill: demand_rate})]. Series = top skills of
    the latest snapshot, identity fixed across the whole chart."""
    if len(history) < 2:
        return ""
    dates = [d for d, _ in history]
    latest = history[-1][1]
    top = sorted(latest, key=lambda s: -latest[s])[:top_n]
    series = [(s, [snap.get(s) for _, snap in history]) for s in top]
    return _line_chart("Skill demand over time",
                       "Demand rate per snapshot · top skills of the latest snapshot",
                       dates, series, "%")


def company_jobs_chart(history: list[tuple[str, dict[str, int]]], top_n: int = 6) -> str:
    """history: [(snapshot_date, {company: open_jobs})]."""
    if len(history) < 2:
        return ""
    dates = [d for d, _ in history]
    latest = history[-1][1]
    top = sorted(latest, key=lambda c: -latest[c])[:top_n]
    series = [(c, [float(snap[c]) if c in snap else None for _, snap in history])
              for c in top]
    return _line_chart("Open jobs by company",
                       "Unique open vacancies per snapshot · largest current employers",
                       dates, series, "")


def write_charts(output_dir: str | Path, current_skills: list[tuple[str, int, float]],
                 jobs_analysed: int, snapshot_date: str,
                 skill_history: list[tuple[str, dict[str, float]]],
                 company_history: list[tuple[str, dict[str, int]]]) -> list[str]:
    """Write chart SVGs; returns report-relative paths of those written."""
    charts_dir = Path(output_dir) / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, svg in [
        ("top_skills.svg", top_skills_bar(current_skills, jobs_analysed, snapshot_date)),
        ("skill_trends.svg", demand_trend_chart(skill_history)),
        ("company_jobs.svg", company_jobs_chart(company_history)),
    ]:
        if svg:
            (charts_dir / name).write_text(svg, encoding="utf-8")
            written.append(f"charts/{name}")
    return written
