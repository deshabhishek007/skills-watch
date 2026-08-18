"""SVG chart generation: structure, gating on history depth, escaping."""

from skills_watch import charts


def test_bar_chart_structure():
    svg = charts.top_skills_bar([("WordPress", 79, 28.1), ("C++ & Rust", 10, 3.6)],
                                jobs_analysed=281, snapshot_date="2026-08-18")
    assert svg.startswith("<svg")
    assert "28.1%" in svg
    assert "C++ &amp; Rust" in svg  # XML-escaped labels


def test_line_charts_need_two_snapshots():
    one = [("2026-08-18", {"PHP": 10.0})]
    assert charts.demand_trend_chart(one) == ""
    assert charts.company_jobs_chart([("2026-08-18", {"Acme": 5})]) == ""


def test_demand_trend_series_and_gaps():
    history = [
        ("2026-08-01", {"PHP": 10.0, "Kubernetes": 12.1}),
        ("2026-08-15", {"PHP": 11.0, "Kubernetes": 16.8, "Rust": 2.0}),
    ]
    svg = charts.demand_trend_chart(history)
    assert "Kubernetes" in svg and "PHP" in svg
    assert "16.8%" in svg  # direct end label with latest value
    # Rust only exists in the latest snapshot — one point, no crash
    assert "Rust" in svg


def test_company_chart_handles_missing_company():
    history = [
        ("2026-08-01", {"Acme": 5}),
        ("2026-08-15", {"Acme": 8, "Globex": 3}),
    ]
    svg = charts.company_jobs_chart(history)
    assert "Acme" in svg and "Globex" in svg
