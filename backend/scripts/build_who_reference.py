"""Build the vendored WHO 2006 LMS reference file used by the anthropometry engine.

The values are the official WHO Child Growth Standards (2006) LMS parameters,
extracted from the tables distributed with the open-source ``pygrowup`` package
(v0.8.2, itself derived from the WHO published tables). This script documents
provenance; the application only needs the generated JSON file.

Usage (one-off, developer machine):
    python scripts/build_who_reference.py --tables <pygrowup>/tables --out data/reference/who_lms.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

INDICATORS = {
    # output key: (young table prefix, older table prefix, age key)
    "hfa": ("lhfa", "lhfa", "Month"),
    "bfa": ("bmifa", "bmifa", "Month"),
}


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def row_key(row: dict, key: str) -> int:
    return int(float(row[key]))


def lms(row: dict) -> dict[str, float]:
    return {"L": float(row["L"]), "M": float(row["M"]), "S": float(row["S"])}


def build_age_table(tables: Path, prefix: str, sex: str, split_month: int = 24) -> dict[str, dict[str, float]]:
    """Months 0..split-1 from the 0-2 table, split..60 from the 2-5 table."""
    young = load(tables / f"{prefix}_{sex}_0_2_zscores.json")
    older = load(tables / f"{prefix}_{sex}_2_5_zscores.json")
    table: dict[str, dict[str, float]] = {}
    for row in young:
        month = row_key(row, "Month")
        if month < split_month:
            table[str(month)] = lms(row)
    for row in older:
        table[str(row_key(row, "Month"))] = lms(row)
    return table


def build_measure_table(tables: Path, filename: str, key: str) -> dict[str, dict[str, float]]:
    rows = load(tables / filename)
    return {str(row_key(row, key)): lms(row) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    reference: dict = {
        "version": "WHO-2006",
        "description": "WHO Child Growth Standards (2006) LMS parameters, 0-60 months.",
        "source": "WHO Child Growth Standards 2006 (tables as published in pygrowup 0.8.2)",
        "license": "WHO growth standards are public; LMS tables reproduced for scientific use.",
        "hfa": {sex: build_age_table(args.tables, "lhfa", sex) for sex in ("boys", "girls")},
        "wfa": {
            sex: {str(row_key(row, "Month")): lms(row) for row in load(args.tables / f"wfa_{sex}_0_5_zscores.json")}
            for sex in ("boys", "girls")
        },
        "bfa": {sex: build_age_table(args.tables, "bmifa", sex) for sex in ("boys", "girls")},
        "wfl": {
            sex: build_measure_table(args.tables, f"wfl_{sex}_0_2_zscores.json", "Length")
            for sex in ("boys", "girls")
        },
        "wfh": {
            sex: build_measure_table(args.tables, f"wfh_{sex}_2_5_zscores.json", "Height")
            for sex in ("boys", "girls")
        },
    }

    # Rename sex keys to M/F for a compact, stable API contract.
    for indicator in ("hfa", "wfa", "bfa", "wfl", "wfh"):
        reference[indicator] = {
            "M": reference[indicator].pop("boys"),
            "F": reference[indicator].pop("girls"),
        }

    # Validation anchors: WHO published -2 SD cut-offs, used by the test suite.
    anchors = {}
    for sex in ("boys", "girls"):
        rows = load(args.tables / f"lhfa_{sex}_0_5_zscores.json")
        anchors[f"hfa_{sex}"] = {str(row_key(r, "Month")): float(r["SD2neg"]) for r in rows}
        rows = load(args.tables / f"wfa_{sex}_0_5_zscores.json")
        anchors[f"wfa_{sex}"] = {str(row_key(r, "Month")): float(r["SD2neg"]) for r in rows}
    reference["validation_minus2sd"] = anchors

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        json.dump(reference, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"written {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
