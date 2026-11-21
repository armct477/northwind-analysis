"""Run all four analyses, then write the output tables and webpage.

Usage: ``python run_analysis.py [--data PATH] [--repo-url URL]``.
"""

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import q1_growth, q2_suppliers, q3_customers, q4_shippers, site
from analysis.data import DATA_PATH, REPO_ROOT, load

DEFAULT_REPO_URL = "https://github.com/armct477/northwind-analysis"
OUTPUT_DIR = REPO_ROOT / "outputs"
SITE_PATH = REPO_ROOT / "docs" / "index.html"


def dataset_facts(nw):
    """Summarize the dataset for the page header and methods notes.

    Args:
        nw (Northwind): Cleaned tables from :func:`analysis.data.load`.

    Returns:
        dict[str, object]: Row count per table, first and last order
        dates (short and long text forms), and the share of order lines
        whose ``UnitPrice`` differs from the product's list price.
    """
    lines = nw.lines.merge(nw.products[["ProductID", "Price"]], on="ProductID", how="left")
    first, last = nw.orders["OrderDate"].min(), nw.orders["OrderDate"].max()
    return {
        "orders": len(nw.orders),
        "lines": len(nw.lines),
        "customers": len(nw.customers),
        "products": len(nw.products),
        "suppliers": len(nw.suppliers),
        "employees": len(nw.employees),
        "shippers": len(nw.shippers),
        "first_date": first.strftime("%b %Y"),
        "last_date": last.strftime("%b %Y"),
        "first_date_long": f"{first.day} {first.strftime('%B %Y')}",
        "last_date_long": f"{last.day} {last.strftime('%B %Y')}",
        "price_differs_share": float((lines["UnitPrice"] != lines["Price"]).mean()),
    }


def to_jsonable(value):
    """Convert analysis results into JSON-serializable values.

    Recurses into dicts, lists and tuples (tuples become lists).

    Args:
        value (object): Value to convert.

    Returns:
        object: Same structure with numpy integers as int, floats
        rounded to 6 decimals (NaN as None), timestamps and dates as
        ISO strings, and dict keys as strings. Other values unchanged.
    """
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if np.isnan(value) else round(float(value), 6)
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    return value


def save_outputs(results, dataset):
    """Write every result table to CSV and all key numbers to JSON.

    Args:
        results (dict[str, dict]): Each question's ``run`` output, keyed
            ``"q1"`` to ``"q4"``.
        dataset (dict[str, object]): Output of :func:`dataset_facts`.

    Returns:
        None. Writes ``outputs/tables/<name>.csv`` and
        ``outputs/key_numbers.json``, overwriting existing files.
    """
    tables_dir = OUTPUT_DIR / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for result in results.values():
        for name, table in result["tables"].items():
            table.to_csv(tables_dir / f"{name}.csv", index=False, encoding="utf-8")
    facts = {key: result["facts"] for key, result in results.items()}
    facts["dataset"] = dataset
    (OUTPUT_DIR / "key_numbers.json").write_text(
        json.dumps(to_jsonable(facts), indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    """Run the full pipeline from the command line.

    Reads ``--data`` and ``--repo-url``, runs Q1 to Q4, saves the
    outputs and writes the webpage to ``docs/index.html``.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(description="Run the Northwind analysis and build the webpage.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Path to the Northwind workbook.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Public GitHub URL shown on the page.")
    args = parser.parse_args()

    nw = load(args.data)
    results = {
        "q1": q1_growth.run(nw),
        "q2": q2_suppliers.run(nw),
        "q3": q3_customers.run(nw),
        "q4": q4_shippers.run(nw),
    }
    dataset = dataset_facts(nw)
    save_outputs(results, dataset)

    SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    page = site.build(results, dataset, args.repo_url, date.today().isoformat())
    SITE_PATH.write_text(page, encoding="utf-8")
    print(f"Wrote {SITE_PATH.relative_to(REPO_ROOT)} and {OUTPUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
