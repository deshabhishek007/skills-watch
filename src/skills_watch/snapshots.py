"""Dated snapshot storage. Historical observations are never overwritten."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


def list_snapshots(snapshots_dir: str | Path) -> list[str]:
    d = Path(snapshots_dir)
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and len(p.name) == 10)


def previous_snapshot(snapshots_dir: str | Path, before_date: str) -> str | None:
    dates = [d for d in list_snapshots(snapshots_dir) if d < before_date]
    return dates[-1] if dates else None


def save_snapshot(output_dir: str | Path, snapshots_dir: str | Path,
                  snapshot_date: str, force: bool = False) -> Path:
    dest = Path(snapshots_dir) / snapshot_date
    if dest.exists():
        if not force:
            raise FileExistsError(
                f"snapshot {snapshot_date} already exists — pass a different "
                f"--snapshot-date or --force-snapshot to replace it"
            )
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in Path(output_dir).glob("*.csv"):
        shutil.copy2(f, dest / f.name)
    report = Path(output_dir) / "report.md"
    if report.exists():
        shutil.copy2(report, dest / "report.md")
    return dest


def load_snapshot_csv(snapshots_dir: str | Path, snapshot_date: str,
                      filename: str) -> list[dict]:
    path = Path(snapshots_dir) / snapshot_date / filename
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
