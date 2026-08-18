"""Taxonomy-driven skill extraction.

A job mentions a skill if the canonical name or any alias appears with word
boundaries in title+description. One job counts a skill once, no matter how
many times it appears.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


def _boundary(pattern: str) -> str:
    # \b doesn't work adjacent to non-word chars (C++, C#, .NET), so use lookarounds.
    return rf"(?<![\w.]){pattern}(?![\w+#])"


class SkillTaxonomy:
    def __init__(self, skills_by_category: dict[str, list[dict]], aliases: dict[str, str]):
        self.category_of: dict[str, str] = {}
        self._patterns: list[tuple[re.Pattern, str]] = []

        for category, entries in skills_by_category.items():
            for entry in entries:
                if isinstance(entry, str):
                    entry = {"name": entry}
                name = entry["name"]
                self.category_of[name] = category
                pattern = entry.get("match") or re.escape(name)
                flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
                self._patterns.append((re.compile(_boundary(pattern), flags), name))

        for alias, canonical in aliases.items():
            if canonical not in self.category_of:
                raise ValueError(f"alias '{alias}' points at unknown skill '{canonical}'")
            # Short all-caps aliases (WP, ML, GCP) stay case-sensitive to avoid
            # matching ordinary words.
            flags = 0 if (alias.isupper() and len(alias) <= 5) else re.IGNORECASE
            self._patterns.append((re.compile(_boundary(re.escape(alias)), flags), canonical))

    @classmethod
    def load(cls, taxonomy_dir: str | Path) -> "SkillTaxonomy":
        taxonomy_dir = Path(taxonomy_dir)
        skills = yaml.safe_load((taxonomy_dir / "skills.yml").read_text(encoding="utf-8"))
        aliases = yaml.safe_load((taxonomy_dir / "skill_aliases.yml").read_text(encoding="utf-8")) or {}
        return cls(skills, aliases)

    def extract(self, text: str) -> list[str]:
        """Return sorted unique canonical skills mentioned in the text."""
        found = {canonical for rx, canonical in self._patterns if rx.search(text)}
        return sorted(found)
