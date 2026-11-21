# Northwind Business Review

Reproducible Python analysis of the Northwind Traders order data, answering four business questions for a general
manager. The output is a single webpage, `docs/index.html`, published with GitHub Pages.

| # | Question | Code |
|---|---|---|
| 1 | Where is growth coming from, and where should sales and promotion effort go? | `analysis/q1_growth.py` |
| 2 | Which suppliers do we depend on most, and where can our volume win better prices? | `analysis/q2_suppliers.py` |
| 3 | Which customers are at risk of leaving, and who should sales call first? | `analysis/q3_customers.py` |
| 4 | Which shipper should get more of our volume, weighing speed against cost? | `analysis/q4_shippers.py` |

## Reproduce everything

Tested with Python 3.13 on Windows. Every number, chart and table on the webpage is produced by one command.

```bash
git clone https://github.com/armct477/northwind-analysis.git
cd northwind-analysis
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_analysis.py
```

This reads `data/Northwind Database.xlsx` and writes:

| Output | What it contains |
|---|---|
| `docs/index.html` | The webpage: all four questions with interactive charts and data tables |
| `outputs/key_numbers.json` | Every number quoted in the page text, grouped by question (`q1` to `q4`, plus `dataset`) |
| `outputs/tables/*.csv` | Every table on the page, and the data behind each chart (file names match the question, e.g. `q3_contact_list.csv`) |

To check a figure on the webpage, find it in `outputs/key_numbers.json` or the matching CSV. To use a different
copy of the workbook, pass `--data path/to/workbook.xlsx`.

## Project layout

```
data/Northwind Database.xlsx   source data (unchanged copy of the course file)
analysis/data.py               loading, cleaning, revenue definition, comparison windows
analysis/q1_growth.py          Q1: revenue bridge, country and category growth, product movers
analysis/q2_suppliers.py       Q2: supplier volume, category share, discontinued-product exposure
analysis/q3_customers.py       Q3: reorder rhythm, at-risk flag, back-test
analysis/q4_shippers.py        Q4: shipping-time distribution, statistical tests, freight-cost regression
analysis/style.py              chart styling and HTML table helper
analysis/site.py               builds the webpage text from the computed results
run_analysis.py                runs everything and writes docs/ and outputs/
```

## Definitions and choices

- **Revenue** = `UnitPrice × Quantity × (1 − Discount)` from the `Orders Details` sheet, using the price charged on
  each order line. Discounts are rounded to 2 decimals to remove float noise such as `0.0500000007`.
- **Cleaning:** the `Product` sheet's leftover columns from an earlier exercise (`Cheap`, `NewPrice`, `Cheap.1`,
  `IsCheap`, `Unnamed: 14`, `NewPrice.1`) are dropped. No rows are removed.
- **Time windows** (`analysis/data.py`): the data runs from 1996-07-04 to 1998-05-06.
  - Q1 compares **Jan–Apr 1997 with Jan–Apr 1998**, the only months observed in both years.
  - Q2 uses **May 1997–Apr 1998** as current annual volume.
  - Q3 measures recency **as of 1998-05-06**.
- **Q2 rule:** among the top 10 suppliers by ongoing sales, a weighted category share of 40% or more means
  "protect"; below 40% means "negotiate". Sales of discontinued products are excluded from volume.
- **Q3 rule:** customers with 3+ orders are flagged as **at risk** at ≥ 3× their median gap between orders, and
  **watch** at 2–3×. The rule is back-tested on monthly cutoffs from Jul 1997 to Jan 1998, with a 120-day
  look-ahead window.
- **Q4 tests:** Kruskal-Wallis and Mann-Whitney tests on days to ship, and chi-square tests on slow (>14 days) and
  late shipments. There's also an OLS with destination-country, order-size and quarter controls (HC1 robust errors),
  plus a log-log freight regression with destination-country effects.

## Limitations

- No purchase-cost data, so profit and margin aren't measured. Q2 uses sales as a proxy for purchase volume.
- Inventory fields are a single snapshot with no history.
- Shipping is measured to the shipment date. The data has no delivery dates.
- About 22 months of history is too short to estimate seasonality.

## Publishing the webpage

In the GitHub repository, go to **Settings → Pages**. Set **Source** to *Deploy from a branch*, choose branch
`main` and folder `/docs`, then save. The page will be served at
`https://armct477.github.io/northwind-analysis/`.
