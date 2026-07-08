#!/usr/bin/env python3
"""
build_dashboard.py

Reads the release/feature tracking Excel file and generates a single
self-contained static HTML dashboard (docs/index.html) for GitHub Pages.

Run manually:
    python build_dashboard.py

Run automatically:
    The GitHub Action in .github/workflows/build.yml runs this every time
    data/dashboard_data.xlsx changes on the main branch.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SOURCE_XLSX = Path("data/dashboard_data.xlsx")
OUTPUT_HTML = Path("docs/index.html")
TEMPLATE_HTML = Path("template.html")

# Canonical column names we expect in the sheet (order matters for display).
# Keys are normalized (lowercased, stripped) source header -> our clean name.
COLUMN_MAP = {
    "component": "Component",
    "module": "Module",
    "sub module": "Sub Module",
    "element": "Element",
    "sub element": "Sub element",
    "user story": "User Story",
    "db": "DB",
    "api": "API",
    "ui": "UI",
    "latest release": "Latest Release",
    "past relase": "Past Release",   # source file has this typo
    "past release": "Past Release",
}

STATUS_SYMBOLS = {
    "\u2713": {"label": "Complete", "key": "complete"},      # ✓
    "\u2666": {"label": "In Progress", "key": "in_progress"},  # ♦
    "\u25cf": {"label": "Not Started", "key": "not_started"},  # ●
    "-": {"label": "N/A", "key": "na"},
}

STATUS_COLUMNS = ["DB", "API", "UI"]
HIERARCHY_COLUMNS = ["Component", "Module", "Sub Module", "Element", "Sub element", "User Story"]


def normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h)).strip().lower()


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, dtype=str)
    df.columns = [normalize_header(c) for c in df.columns]
    rename = {c: COLUMN_MAP[c] for c in df.columns if c in COLUMN_MAP}
    df = df.rename(columns=rename)

    missing = [v for v in set(COLUMN_MAP.values()) if v not in df.columns]
    if missing:
        raise ValueError(
            f"Excel file is missing expected column(s): {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    for col in HIERARCHY_COLUMNS + STATUS_COLUMNS + ["Latest Release", "Past Release"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df


def status_key(symbol: str) -> str:
    return STATUS_SYMBOLS.get(symbol.strip(), {"key": "unknown"})["key"]


def build_records(df: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        rec = {col: row[col] for col in HIERARCHY_COLUMNS}
        rec["Latest Release"] = row["Latest Release"]
        rec["Past Release"] = row["Past Release"]
        for col in STATUS_COLUMNS:
            symbol = row[col]
            rec[col] = symbol
            rec[f"{col}_status"] = status_key(symbol)
        records.append(rec)
    return records


def build_summary(df: pd.DataFrame) -> dict:
    total = len(df)
    summary = {"total": total, "columns": {}}
    for col in STATUS_COLUMNS:
        counts = {"complete": 0, "in_progress": 0, "not_started": 0, "na": 0, "unknown": 0}
        for symbol in df[col]:
            counts[status_key(symbol)] += 1
        pct_complete = round(100 * counts["complete"] / total, 1) if total else 0.0
        summary["columns"][col] = {"counts": counts, "pct_complete": pct_complete}

    summary["components"] = sorted(df["Component"].unique().tolist())
    summary["modules"] = sorted(df["Module"].unique().tolist())
    summary["releases"] = sorted(
        {r for r in df["Latest Release"].unique().tolist() if r}
    )
    return summary


def main():
    if not SOURCE_XLSX.exists():
        raise SystemExit(f"Source file not found: {SOURCE_XLSX}")

    df = load_data(SOURCE_XLSX)
    records = build_records(df)
    summary = build_summary(df)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": records,
        "summary": summary,
    }

    template = TEMPLATE_HTML.read_text(encoding="utf-8")
    html = template.replace(
        "__DASHBOARD_DATA_JSON__",
        json.dumps(payload, ensure_ascii=False),
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML} ({len(records)} rows, generated {payload['generated_at']})")


if __name__ == "__main__":
    main()
