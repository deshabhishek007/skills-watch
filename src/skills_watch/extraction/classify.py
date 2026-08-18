"""Rule-based classifiers for job function, seniority, remote status and location."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


class RuleClassifier:
    """Ordered first-match-wins keyword rules loaded from a taxonomy YAML."""

    def __init__(self, rules: list[dict], default: str = "Unknown"):
        self.default = default
        self._rules = [
            (r["name"], [re.compile(p, self._flags(p)) for p in r["patterns"]])
            for r in rules
        ]

    @staticmethod
    def _flags(pattern: str) -> int:
        # Acronym patterns like "\bSRE\b" stay case-sensitive so they don't
        # match ordinary words; everything else is case-insensitive.
        core = re.sub(r"\\[bB]", "", pattern)
        return 0 if (core.isupper() and len(core) <= 5) else re.IGNORECASE

    @classmethod
    def load(cls, path: str | Path, key: str, default: str = "Unknown") -> "RuleClassifier":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(data[key], default=default)

    def classify(self, *texts: str | None) -> str:
        for text in texts:
            if not text:
                continue
            for name, patterns in self._rules:
                if any(p.search(text) for p in patterns):
                    return name
        return self.default


REMOTE_RX = re.compile(r"\b(remote|anywhere|work from home|distributed)\b", re.IGNORECASE)
HYBRID_RX = re.compile(r"\bhybrid\b", re.IGNORECASE)
ONSITE_RX = re.compile(r"\b(on-?site|in-?office|office-based)\b", re.IGNORECASE)


def classify_remote(location: str | None, title: str, description: str | None,
                    ats_remote_status: str | None = None) -> str:
    """Remote / Hybrid / On-site / Unknown. ATS-provided flags win; then the
    location string; the description is only trusted for hybrid/remote phrasing
    near the top (full descriptions mention 'remote' too loosely)."""
    if ats_remote_status:
        return ats_remote_status
    for text in (location, title):
        if text:
            if HYBRID_RX.search(text):
                return "Hybrid"
            if REMOTE_RX.search(text):
                return "Remote"
            if ONSITE_RX.search(text):
                return "On-site"
    if location:
        return "On-site"  # a concrete location with no remote/hybrid marker
    head = (description or "")[:500]
    if HYBRID_RX.search(head):
        return "Hybrid"
    if REMOTE_RX.search(head):
        return "Remote"
    return "Unknown"


COUNTRY_HINTS = [
    ("Worldwide", r"\b(worldwide|anywhere|global)\b"),
    ("United States", r"\b(united states|usa|u\.s\.|\bUS\b|remote.?[-,]? ?us)\b"),
    ("United Kingdom", r"\b(united kingdom|\bUK\b|london|manchester)\b"),
    ("India", r"\b(india|bangalore|bengaluru|mumbai|pune|hyderabad|chennai|delhi|gurgaon|noida)\b"),
    ("Canada", r"\b(canada|toronto|vancouver|montreal)\b"),
    ("Europe", r"\b(europe|EMEA|germany|berlin|netherlands|amsterdam|spain|madrid|barcelona|france|paris|poland|warsaw|portugal|lisbon|bulgaria|sofia|plovdiv|stara zagora|norway|oslo|armenia|yerevan|ukraine|kyiv|romania|serbia|greece|athens|italy|ireland|dublin)\b"),
    ("APAC", r"\b(APAC|australia|sydney|melbourne|singapore|japan|tokyo|philippines|manila)\b"),
    ("Latin America", r"\b(LATAM|latin america|brazil|mexico|argentina|colombia)\b"),
]


def normalise_location(location: str | None) -> str:
    """Coarse geography from raw location text. Raw text is preserved on the job."""
    if not location:
        return "Unknown"
    for region, pattern in COUNTRY_HINTS:
        if re.search(pattern, location, re.IGNORECASE):
            return region
    return "Other"
