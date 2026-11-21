"""Build the single-page HTML report from the analysis results."""

import html

from . import style
from .style import money, money_k, pct

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --ink-muted: #898781;
  --hairline: #e1e0d9;
  --accent: #2a78d6;
  --accent-wash: rgba(42, 120, 214, 0.07);
  --font: system-ui, -apple-system, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--page); }
body { margin: 0; background: var(--page); color: var(--ink); font-family: var(--font); line-height: 1.6;
       font-size: 17px; -webkit-text-size-adjust: 100%; }
a { color: var(--accent); }
.wrap { max-width: 960px; margin: 0 auto; padding: 0 16px; }
header.hero { padding: 48px 0 24px; }
.eyebrow { color: var(--ink-muted); font-size: 14px; letter-spacing: .02em; margin: 0 0 8px; }
h1 { font-size: clamp(28px, 4.5vw, 40px); line-height: 1.15; margin: 0 0 12px; letter-spacing: -.01em; }
.lede { color: var(--ink-2); font-size: 19px; margin: 0; max-width: 46em; }
nav.toc { position: sticky; top: 0; z-index: 5; background: rgba(249, 249, 247, .94);
          backdrop-filter: blur(6px); border-bottom: 1px solid var(--hairline); }
nav.toc .wrap { display: flex; gap: 20px; overflow-x: auto; padding-top: 10px; padding-bottom: 10px;
                white-space: nowrap; font-size: 15px; }
nav.toc a { color: var(--ink-2); text-decoration: none; }
nav.toc a:hover { color: var(--accent); }
.takeaways { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 24px 0 8px; }
.takeaway { background: var(--surface); border: 1px solid var(--hairline); border-radius: 10px; padding: 16px; }
.takeaway .label { color: var(--ink-muted); font-size: 13px; margin: 0 0 4px; }
.takeaway .value { font-size: 28px; font-weight: 600; margin: 0 0 6px; line-height: 1.2; }
.takeaway p { margin: 0; font-size: 15px; color: var(--ink-2); line-height: 1.45; }
section.question { padding: 40px 0 8px; border-top: 1px solid var(--hairline); margin-top: 32px; }
.qnum { color: var(--accent); font-weight: 600; font-size: 14px; margin: 0 0 6px; letter-spacing: .03em; }
h2 { font-size: clamp(22px, 3.2vw, 28px); line-height: 1.25; margin: 0 0 20px; letter-spacing: -.005em; }
h3 { font-size: 15px; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-muted); margin: 28px 0 8px; }
p { margin: 0 0 12px; }
ul { margin: 0 0 12px; padding-left: 22px; }
li { margin-bottom: 6px; }
figure { margin: 20px 0 24px; background: var(--surface); border: 1px solid var(--hairline); border-radius: 10px;
         padding: 16px 12px 12px; }
figcaption .title { font-weight: 600; font-size: 16px; color: var(--ink); margin: 0 4px 2px; }
figcaption .sub { color: var(--ink-2); font-size: 14px; margin: 0 4px 8px; }
.note { color: var(--ink-muted); font-size: 13px; margin: 8px 4px 0; }
/* Charts keep a readable minimum width; on phones they scroll sideways inside their card. */
.plot-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.plot-inner { min-width: 680px; }
.scroll-hint { display: none; color: var(--ink-muted); font-size: 13px; margin: 0 4px 6px; }
.callout { background: var(--accent-wash); border-left: 3px solid var(--accent); border-radius: 0 8px 8px 0;
           padding: 14px 18px; margin: 8px 0 16px; }
.callout p:last-child, .callout ul:last-child { margin-bottom: 0; }
details { margin: 10px 4px 0; }
details summary { cursor: pointer; color: var(--accent); font-size: 14px; }
.table-wrap { overflow-x: auto; margin: 10px 0 4px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; background: var(--surface); }
caption { text-align: left; color: var(--ink-2); font-size: 14px; padding: 0 0 6px; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--hairline); text-align: left; vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; background: #f4f3ef; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.methods { font-size: 15px; color: var(--ink-2); }
footer { padding: 32px 0 56px; color: var(--ink-muted); font-size: 14px; border-top: 1px solid var(--hairline); margin-top: 40px; }
@media (max-width: 720px) {
  .scroll-hint { display: block; }
}
@media (max-width: 600px) {
  body { font-size: 16px; }
  header.hero { padding-top: 32px; }
  figure { padding: 12px 6px 8px; }
}
"""


def esc(text):
    """Escape text for safe use in HTML.

    Args:
        text (object): Value to show; converted with ``str``.

    Returns:
        str: HTML-escaped text.
    """
    return html.escape(str(text))


def join_names(names):
    """Join names into an English list ("A, B and C").

    Args:
        names (Iterable[object]): Items to join; each is HTML-escaped.

    Returns:
        str: Escaped list with commas and "and" before the last item;
        an empty string for no items.
    """
    names = [esc(n) for n in names]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def num(n):
    """Spell out a small count for use in prose.

    Args:
        n (int | float): Count; converted with ``int`` (truncates).

    Returns:
        str: Word for 0 to 10 (``"six"``); otherwise digits with
        thousands separators, including for negative numbers.
    """
    # Spell out small counts in prose ("six suppliers"), keep digits above ten.
    n = int(n)
    return NUMBER_WORDS[n] if 0 <= n <= 10 else f"{n:,}"


def cap(text):
    """Capitalize the first character, leaving the rest unchanged.

    Args:
        text (str): Text to capitalize.

    Returns:
        str: ``text`` with its first character upper-cased.
    """
    return text[:1].upper() + text[1:]


def countries(names):
    """Join country names for prose, adding "the" before USA and UK.

    Args:
        names (Iterable[str]): Country names as stored in the data.

    Returns:
        str: Escaped English list, e.g. "the USA, Germany and Brazil".
    """
    return join_names([{"USA": "the USA", "UK": "the UK"}.get(n, n) for n in names])


def figure_block(fig, div_id, title, subtitle, data_table=None, note=None, data_label="Show the data"):
    """Wrap a chart in a captioned figure with an optional data table.

    Args:
        fig (plotly.graph_objects.Figure): Chart to embed.
        div_id (str): ``id`` for the chart's ``<div>``.
        title (str): Figure title; inserted as HTML, not escaped.
        subtitle (str): Line under the title; inserted as HTML.
        data_table (str | None): HTML table shown in a collapsible
            section; None for none.
        note (str | None): Small note under the chart; None for none.
        data_label (str): Text of the collapsible section's toggle.

    Returns:
        str: HTML ``<figure>`` element.
    """
    parts = [
        "<figure>",
        f'<figcaption><p class="title">{title}</p><p class="sub">{subtitle}</p></figcaption>',
        '<p class="scroll-hint">Swipe sideways to see the full chart →</p>',
        f'<div class="plot-scroll"><div class="plot-inner">{style.figure_html(fig, div_id)}</div></div>',
    ]
    if note:
        parts.append(f'<p class="note">{note}</p>')
    if data_table:
        parts.append(f"<details><summary>{data_label}</summary>{data_table}</details>")
    parts.append("</figure>")
    return "\n".join(parts)


def section(anchor, number, question, why, approach, body, finding, implications):
    """Assemble one question's section of the page.

    All inputs are inserted as HTML without escaping.

    Args:
        anchor (str): ``id`` targeted by the navigation links.
        number (int): Question number shown above the heading.
        question (str): Question text, used as the heading.
        why (str): "Why it matters" paragraph.
        approach (list[str]): Approach bullet points.
        body (str): HTML for the figures and tables.
        finding (str): HTML paragraphs for the "Main finding" callout.
        implications (list[str]): "Business implication" bullets.

    Returns:
        str: HTML ``<section>`` element.
    """
    approach_html = "<ul>" + "".join(f"<li>{a}</li>" for a in approach) + "</ul>"
    impl_html = "<ul>" + "".join(f"<li>{i}</li>" for i in implications) + "</ul>"
    return f"""
<section class="question" id="{anchor}">
  <p class="qnum">QUESTION {number}</p>
  <h2>{question}</h2>
  <h3>Why it matters</h3>
  <p>{why}</p>
  <h3>Approach</h3>
  {approach_html}
  {body}
  <h3>Main finding</h3>
  <div class="callout">{finding}</div>
  <h3>Business implication</h3>
  {impl_html}
</section>"""


def money_fmt(v):
    """Format a table value as whole dollars.

    Args:
        v (float): Amount in USD.

    Returns:
        str: For example ``"$1,555"``.
    """
    return money(v)


def pct_fmt(v):
    """Format a fraction as a percentage with one decimal.

    Args:
        v (float): Fraction, e.g. 0.149.

    Returns:
        str: For example ``"14.9%"``.
    """
    return pct(v, 1)


def pct0_fmt(v):
    """Format a fraction as a whole percentage.

    Args:
        v (float): Fraction, e.g. 0.56.

    Returns:
        str: For example ``"56%"``.
    """
    return pct(v)


def signed_pct_fmt(v):
    """Format a fraction as a whole percentage with a sign.

    Args:
        v (float): Fraction, e.g. 1.21 or -0.42.

    Returns:
        str: For example ``"+121%"`` or ``"−42%"``.
    """
    return pct(v, signed=True)


def q1_section(r):
    """Build the Q1 (growth) section of the page.

    Args:
        r (dict[str, dict]): Output of :func:`analysis.q1_growth.run`.

    Returns:
        str: HTML ``<section>`` with the question, approach, charts,
        tables, finding and implications.
    """
    f, t, fig = r["facts"], r["tables"], r["figures"]
    cg = f["category_growth"]
    drivers = t["q1_drivers"].copy()
    drivers_fmt = {}
    for col in drivers.columns[1:3]:
        drivers[col] = [
            money(v) if m in ("Revenue", "Average order value") else (f"{v:.2f}" if m == "Orders per customer" else f"{v:,.0f}")
            for m, v in zip(drivers["Measure"], drivers[col])
        ]
    drivers_fmt["Change"] = signed_pct_fmt
    drivers_html = table_html_safe(drivers, drivers_fmt, numeric=list(drivers.columns[1:]),
                                   caption="What changed between the two windows")

    money_cols = lambda df: {c: money_fmt for c in df.columns if c in ("Jan–Apr 1997", "Jan–Apr 1998", "Change", "Revenue change", "Revenue")}
    bridge_t = t["q1_bridge"]
    bridge_html = table_html_safe(bridge_t, {"Revenue change": money_fmt, "Customers": lambda v: f"{v:.0f}"})
    country_t = t["q1_country"].copy()
    country_t["Growth"] = country_t["Growth"].astype(object).where(country_t["Growth"].notna(), "new market")
    country_html = table_html_safe(country_t, {
        **money_cols(country_t),
        "Growth": lambda v: v if isinstance(v, str) else signed_pct_fmt(v),
        "Share of growth": pct_fmt,
    })
    cat_t = t["q1_category"]
    cat_html = table_html_safe(cat_t, {**money_cols(cat_t), "Growth": signed_pct_fmt, "Share of growth": pct_fmt})
    movers_fmt = lambda df: {**money_cols(df), "Growth": signed_pct_fmt}
    gainers_html = table_html_safe(t["q1_gainers"], movers_fmt(t["q1_gainers"]),
                                   caption="Five products that added the most revenue")
    decliners_html = table_html_safe(t["q1_decliners"], movers_fmt(t["q1_decliners"]),
                                     caption="Five products that lost the most revenue")
    monthly_html = table_html_safe(t["q1_monthly"].assign(Month=t["q1_monthly"]["Month"].dt.strftime("%b %Y")),
                                   {"Revenue": money_fmt})

    body = "\n".join([
        figure_block(fig["q1_monthly"], "fig-q1-monthly", "Revenue has been accelerating since late 1997",
                     "Monthly revenue, Jul 1996 – Apr 1998. Shaded: the two four-month windows compared below.",
                     monthly_html, note="May 1998 is excluded because the data stops on 6 May."),
        drivers_html,
        figure_block(fig["q1_bridge"], "fig-q1-bridge", "Most of the increase came from customers Northwind already had",
                     "Revenue bridge from Jan–Apr 1997 to Jan–Apr 1998, split by type of customer (USD).",
                     bridge_html,
                     note="Gray bars are the two totals; blue bars add revenue and red bars subtract it. "
                          "Existing = bought in both windows. New = first order after April 1997. "
                          "Won back = older customer who skipped Jan–Apr 1997. "
                          "Stopped buying = ordered in Jan–Apr 1997 but not in Jan–Apr 1998."),
        figure_block(fig["q1_country"], "fig-q1-country", "Three markets delivered more than half of the growth",
                     "Change in revenue by customer country, Jan–Apr 1997 to Jan–Apr 1998 (USD).", country_html),
        figure_block(fig["q1_category"], "fig-q1-category", "Seafood, Beverages and Dairy are outgrowing the company",
                     "Revenue growth by product category vs company growth, Jan–Apr 1997 to Jan–Apr 1998.",
                     cat_html),
        gainers_html,
        decliners_html,
    ])

    finding = (
        f"<p>Revenue grew <strong>{pct(f['company_growth'])}</strong> "
        f"({money_k(f['prior_total'])} to {money_k(f['current_total'])}). "
        f"<strong>Existing customers ordering more often</strong> drove it: they added a net "
        f"{money_k(f['existing_net'])}, or {pct(f['existing_share'])} of the increase. Orders per customer rose from "
        f"{f['orders_per_customer_prior']:.1f} to {f['orders_per_customer_current']:.1f}, but the average order grew only "
        f"{pct(f['aov_growth'])}. The {num(f['new_customers'])} new customers added just {money_k(f['new_change'])}.</p>"
        f"<p>{cap(countries(f['top3_countries']))} produced {pct(f['top3_share'])} of the growth. France was flat "
        f"({pct(f['france_growth'], signed=True)} on a {money_k(f['france_prior'])} base), and "
        f"{countries(f['declining_countries'])} shrank. {join_names(f['faster_categories'])} grew faster than the "
        f"company. {join_names(f['slower_categories'][:3])} lagged well behind it, with Grains/Cereals growing only "
        f"{pct(cg['Grains/Cereals'])}.</p>"
        f"<p>The biggest single gainer was {esc(f['top_product'])} (+{money_k(f['top_product_change'])}). Close "
        f"behind was {join_names(f['discontinued_gainers'])} (+{money_k(f['discontinued_gainers_change'][0])}), "
        f"which has since been discontinued.</p>"
    )
    discontinued_name = join_names(f["discontinued_gainers"])
    discontinued_category = esc(f["discontinued_gainers_category"][0])
    implications = [
        "<strong>Keep deepening existing accounts, while still winning new ones.</strong> Existing customers ordering "
        "more often drove most of the growth, so regular reorder check-ins with established accounts should stay a "
        f"priority, especially in {countries(f['top3_countries'])}. Question 3 shows which accounts to call first. "
        f"New and won-back customers still added {money_k(f['new_change'] + f['won_back_change'])}, though, so "
        "prospecting for new customers should continue alongside.",
        f"<strong>Diagnose the stalled markets.</strong> France is flat and {countries(f['declining_countries'])} are "
        "shrinking. Question 3 finds several French customers have gone quiet.",
        "<strong>Aim promotions at the lagging categories, and expand the fast-growing ones.</strong> Promotions can "
        f"lift {join_names(f['slower_categories'][:3])}, where demand isn't keeping pace. "
        f"{join_names(f['faster_categories'])} show strong demand, so adding new products in these categories "
        "could capture more of it.",
        f"<strong>Find out why {discontinued_name} was discontinued.</strong> It was one of the biggest gainers "
        f"(+{money_k(f['discontinued_gainers_change'][0])}). Unless Northwind is deliberately phasing out "
        f"{discontinued_category}, it should source the product or an equivalent from another supplier so this "
        f"demand isn't lost. Question 2 shows {discontinued_category} has almost no active products left.",
    ]
    approach = [
        "Compared <strong>Jan–Apr 1997 with Jan–Apr 1998</strong>. These are the only months observed in both "
        "years: the data starts in July 1996 and ends on 6 May 1998, so calendar years would mislead.",
        "Revenue = unit price × quantity × (1 − discount), using the price actually charged on each order line.",
        "Split the revenue change three ways: by <strong>type of customer</strong> (existing, new, won back, stopped "
        "buying), by <strong>customer country</strong>, and by <strong>product category and product</strong>, "
        "comparing each category with the company's overall growth.",
    ]
    why = ("Revenue more than doubled in a year. Knowing whether that came from new accounts or existing ones, and from "
           "which markets and product lines, shows where extra sales and promotion effort will pay off. It also shows "
           "where growth is fragile.")
    return section("growth", 1, "Where is growth coming from, and where should sales and promotion effort go?",
                   why, approach, body, finding, implications)


def table_html_safe(df, formats, numeric=None, caption=None):
    """Render a table with :func:`analysis.style.table_html`.

    Args:
        df (pandas.DataFrame): Table to render.
        formats (dict[str, Callable]): Column name to formatter.
        numeric (Iterable[str] | None): Columns to right-align; None
            means every numeric column.
        caption (str | None): Table caption; None for no caption.

    Returns:
        str: HTML table.
    """
    return style.table_html(df, formats=formats, numeric=numeric, caption=caption)


def q2_section(r, f1, dataset):
    """Build the Q2 (suppliers) section of the page.

    Args:
        r (dict[str, dict]): Output of
            :func:`analysis.q2_suppliers.run`.
        f1 (dict[str, object]): Q1 ``facts``, used to cite the top
            product's share of growth.
        dataset (dict[str, object]): Dataset summary from
            ``run_analysis.dataset_facts``; supplies the supplier
            count.

    Returns:
        str: HTML ``<section>`` with the question, approach, charts,
        tables, finding and implications.
    """
    f, t, fig = r["facts"], r["tables"], r["figures"]
    n_negotiate, n_protect = len(f["negotiate_names"]), len(f["protect_names"])
    top = t["q2_top_suppliers"]
    top_html = table_html_safe(top, {
        "Ongoing sales": money_fmt, "Share of ongoing sales": pct_fmt, "Share of category": pct0_fmt,
        "Sales of discontinued products": money_fmt,
    }, caption="Top 10 suppliers by ongoing sales, May 1997–Apr 1998")
    all_html = table_html_safe(t["q2_all_suppliers"], {
        "Ongoing sales": money_fmt, "Share of category": pct0_fmt, "Sales of discontinued products": money_fmt})
    cat_html = table_html_safe(t["q2_categories"], {
        "Products still sold": money_fmt, "Products now discontinued": money_fmt, "Discontinued share": pct0_fmt})

    body = "\n".join([
        figure_block(fig["q2_leverage"], "fig-q2-leverage",
                     f"{cap(num(n_negotiate))} large suppliers are replaceable; {num(n_protect)} are not",
                     "Each dot is a supplier. Horizontal: Northwind's sales of its products that are still sold "
                     "(proxy for purchase volume). Vertical: its share of its category's sales.",
                     all_html, data_label="Show all suppliers"),
        top_html,
        figure_block(fig["q2_categories"], "fig-q2-categories",
                     "Meat/Poultry has almost run out of active products",
                     "Sales by category, May 1997–Apr 1998, split by whether the product is still sold (USD).",
                     cat_html),
    ])
    negotiate = join_names(f["negotiate_names"])
    protect = join_names(f["protect_names"])
    finding = (
        f"<p>The top {f['top_n']} suppliers account for <strong>{pct(f['top_share'])}</strong> of ongoing sales. "
        f"<strong>{cap(num(n_negotiate))} of them</strong> ({negotiate}) together sell {money_k(f['negotiate_total'])} a year through "
        f"Northwind ({pct(f['negotiate_share'])} of ongoing sales). None holds more than "
        f"{pct(f['negotiate_max_share'])} of its category, so Northwind could credibly move volume to a competitor. "
        f"These are the best candidates for volume discounts.</p>"
        f"<p>The other {num(n_protect)} ({protect}) each hold {pct(f['protect_min_share'])}–{pct(max(f['protect_shares']))} "
        f"of their category, worth {money_k(f['protect_total'])} a year. Customers concentrate their spending on "
        f"these suppliers' products, so pushing hard on price risks those sales.</p>"
        f"<p>The biggest supply risk is <strong>Meat/Poultry</strong>: {pct(f['meat_discontinued_share'])} of the "
        f"last 12 months' {money_k(f['meat_total'])} in Meat/Poultry sales came from products that are now "
        f"discontinued. Only {esc(f['meat_supplier'])} ({num(len(f['meat_active_products']))} products) still supplies active meat "
        f"products.</p>"
    )
    implications = [
        f"<strong>Open volume-discount talks with the {num(n_negotiate)} replaceable suppliers</strong>, starting with "
        f"the largest ({join_names(f['negotiate_names'][:2])}). Their products bring in "
        f"{money_k(f['negotiate_total'])} of sales a year, so every 1% off the purchase price saves a little under "
        f"{money_k(f['negotiate_total'] * 0.01)} a year. Purchase costs are lower than these sales figures.",
        f"<strong>Protect the {num(n_protect)} dominant suppliers rather than squeezing them.</strong> Secure multi-year "
        f"terms and qualify a second source, especially for {esc(f['protect_names'][0])}. Its "
        f"{esc(f1['top_product'])} also drove {pct(f1['top_product_share'])} of all growth (Question 1).",
        f"<strong>Find a new Meat/Poultry supplier now.</strong> About {money_k(f['meat_discontinued'])} of the last "
        "12 months' sales came from discontinued meat products, and that revenue will be lost once their remaining "
        "stock runs out.",
        f"<strong>Consolidate Seafood buying.</strong> {money_k(f['seafood_total'])} of Seafood sales is spread across "
        f"{num(f['seafood_suppliers'])} suppliers, none above {pct(f['seafood_largest_share'])} of the category. Fewer "
        "suppliers would create the volume needed for better terms.",
    ]
    approach = [
        "Used the last 12 complete months (<strong>May 1997–Apr 1998</strong>) as current annual volume.",
        "The data has no purchase costs, so <strong>Northwind's sales of each supplier's products are a proxy for "
        "how much it buys</strong> from them. Discontinued products are excluded from this volume because they "
        "won't be bought again.",
        "Measured how replaceable each supplier is by its <strong>share of its category's sales</strong> (weighted "
        "when it supplies several categories), plus the number of other suppliers with active products there.",
        f"Rule: among the top {f['top_n']} suppliers by volume, a category share under 40% means negotiate, and 40% or "
        f"more means protect. No top-10 supplier falls between {pct(f['negotiate_max_share'])} and "
        f"{pct(f['protect_min_share'])}, so the result doesn't hinge on the exact cut-off.",
    ]
    why = (f"Northwind resells products from {dataset['suppliers']} suppliers. Purchasing terms are one of the few levers that improve "
           "margin without raising prices. Where Northwind is a large customer and could switch, it can ask for "
           "volume discounts. Where it can't easily switch, it needs to protect the relationship instead.")
    return section("suppliers", 2, "Which suppliers do we depend on most, and where can our volume win better prices?",
                   why, approach, body, finding, implications)


def q3_section(r):
    """Build the Q3 (customers at risk) section of the page.

    Args:
        r (dict[str, dict]): Output of
            :func:`analysis.q3_customers.run`.

    Returns:
        str: HTML ``<section>`` with the question, approach, chart,
        tables, finding and implications.
    """
    f, t, fig = r["facts"], r["tables"], r["figures"]
    contact_fmt = {"Usual gap (days)": lambda v: f"{v:.0f}", "Overdue (× usual gap)": lambda v: f"{v:.1f}×",
                   "Revenue, last 12 months": money_fmt}
    contact_html = table_html_safe(t["q3_contact_list"], contact_fmt,
                                   caption="Call list: customers flagged as at risk or on watch, as of 6 May 1998")
    backtest_html = table_html_safe(t["q3_backtest"], {f"Ordered again within {f['backtest_horizon']} days": pct0_fmt},
                                    caption="Back-test: share who ordered again within 120 days, by status at each monthly cutoff (Jul 1997 – Jan 1998)")
    sens_html = table_html_safe(t["q3_sensitivity"], {"Revenue, last 12 months": money_fmt,
                                                      "Threshold (× usual gap)": lambda v: f"{v:g}×"},
                                caption="How the list changes with the threshold")
    all_html = table_html_safe(t["q3_all_customers"], contact_fmt)

    body = "\n".join([
        figure_block(fig["q3_risk"], "fig-q3-risk",
                     "A handful of regular customers have gone unusually quiet",
                     "Each bubble is a customer with 3+ orders. Bubble area = revenue in the last 12 months. "
                     "Customers above the 3× line are at risk.",
                     all_html, data_label="Show all 86 customers"),
        contact_html,
        backtest_html,
        f"<details><summary>Threshold sensitivity</summary>{sens_html}</details>",
    ])
    names = f["top_at_risk"]
    finding = (
        f"<p><strong>{cap(num(f['at_risk_count']))} customers are at risk</strong> ({money_k(f['at_risk_revenue'])} in "
        f"the last 12 months, {pct(f['at_risk_share'], 1)} of revenue), and {num(f['watch_count'])} more are on watch. "
        f"The top priority is <strong>{esc(names[0])}</strong> ({esc(f['top_at_risk_country'][0])}). It usually "
        f"orders every {f['top_at_risk_gap'][0]:.0f} days but hasn't ordered for {f['top_at_risk_days'][0]} days, "
        f"after buying {money_k(f['top_at_risk_revenue'][0])} in the last 12 months.</p>"
        f"<p><strong>{cap(num(f['france_flagged']))} of the {num(f['flagged_count'])} flagged customers are in "
        f"France</strong>, which is consistent with France's flat revenue in Question 1. Their combined Jan–Apr "
        f"revenue fell from "
        f"{money_k(f['france_flagged_prior_window'])} in 1997 to {money_k(f['france_flagged_current_window'])} in 1998.</p>"
        f"<p>The back-test supports the at-risk flag, but it's a warning, not a verdict: "
        f"{pct(f['backtest_at_risk_reorder'])} of customers flagged at risk still ordered within "
        f"{f['backtest_horizon']} days, against {pct(f['backtest_on_track_reorder'])} of on-track customers. So the "
        f"flag nearly doubles the chance a customer doesn't come back ({pct(1 - f['backtest_at_risk_reorder'])} vs "
        f"{pct(1 - f['backtest_on_track_reorder'])}). Customers at 2–3× their usual gap reordered about as often "
        f"as on-track ones ({pct(f['backtest_watch_reorder'])}), so the watch tier is lower priority. We also "
        f"checked whether customers who deal with many different salespeople are more likely to be overdue, and "
        f"found no meaningful link (correlation {f['rep_rho']:.2f}, not statistically significant).</p>"
    )
    implications = [
        f"<strong>Call the {num(f['at_risk_count'])} at-risk customers this week, in revenue order,</strong> "
        f"starting with {join_names(names)}. The {num(f['at_risk_count'])} together bought "
        f"{money_k(f['at_risk_revenue'])} in the last 12 months.",
        "<strong>Match the retention offer to the account.</strong> In the back-test, about "
        f"{pct(f['backtest_at_risk_reorder'])} of customers flagged at risk ordered again within "
        f"{f['backtest_horizon']} days anyway, so start with a call or a "
        "reorder reminder. For valuable accounts that are far overdue or don't respond, a targeted discount to win "
        f"them back may be worth it. {esc(names[0])}, at {f['top_at_risk_overdue'][0]:.1f}× its usual gap, is "
        "the clearest case.",
        f"<strong>Look at France as a market, not just individual accounts.</strong> {cap(num(f['france_flagged']))} "
        f"of the {num(f['flagged_count'])} flagged customers are French.",
        "<strong>Run this list every month.</strong> The rule uses only order dates, so it's cheap to refresh as new "
        "orders arrive, and it catches accounts drifting away before they're gone.",
    ]
    approach = [
        f"For each of the {f['eligible']} customers with <strong>at least three orders</strong>, found their usual "
        "gap between orders (the median), then compared it with the days since their last order. "
        "\"Today\" is 6 May 1998, the last date in the data.",
        f"<strong>At risk</strong> = at least {f['at_risk_multiple']:g}× the usual gap. "
        f"<strong>Watch</strong> = {f['watch_multiple']:g}–{f['at_risk_multiple']:g}×. Within each group, "
        "customers are ranked by revenue in the last 12 months.",
        f"<strong>Back-tested the rule</strong> by applying it on the first day of each month from July 1997 to "
        f"January 1998 ({f['backtest_snapshots']} customer snapshots) and checking who ordered within the next "
        f"{f['backtest_horizon']} days.",
        f"Excluded {num(len(f['thin_names']))} customers with fewer than three orders, which isn't enough to know "
        f"their rhythm, and {num(f['never_ordered'])} customers who have never ordered.",
    ]
    why = ("Question 1 showed that growth comes mostly from existing customers ordering more often, so losing "
           "an established account is costly. The cheapest time to keep a customer is before they have clearly left. "
           "A short, ranked call list lets sales act early.")
    return section("customers", 3, "Which customers are at risk of leaving, and who should sales call first?",
                   why, approach, body, finding, implications)


def q4_section(r):
    """Build the Q4 (shippers) section of the page.

    Args:
        r (dict[str, dict]): Output of
            :func:`analysis.q4_shippers.run`.

    Returns:
        str: HTML ``<section>`` with the question, approach, charts,
        tables, finding and implications.
    """
    f, t, fig = r["facts"], r["tables"], r["figures"]
    s = f["summary"]
    fed, ups, spd = s["Federal Shipping"], s["United Package"], s["Speedy Express"]
    cost = f["cost"]["Federal Shipping"]
    slow_col = f"Share taking over {f['slow_days']} days"
    summary = t["q4_summary"][["Shipper", "Orders", "Share of orders", "Median days to ship",
                               "90% shipped within (days)", slow_col, "Late vs required date", "Average freight"]]
    summary_html = table_html_safe(summary, {
        "Share of orders": pct0_fmt, "Median days to ship": lambda v: f"{v:.0f}",
        "90% shipped within (days)": lambda v: f"{v:.0f}", slow_col: pct_fmt, "Late vs required date": pct_fmt,
        "Average freight": lambda v: money(v, 2)}, caption="Carrier scorecard, Jul 1996 – May 1998")
    share_html = table_html_safe(t["q4_share_by_year"], {c: pct0_fmt for c in t["q4_share_by_year"].columns[1:]},
                                 caption="Share of orders by carrier")
    cost_t = t["q4_cost"][["Shipper", "Freight for the same orders (United = $100)", "Likely range low",
                           "Likely range high"]]
    cost_html = table_html_safe(cost_t, {c: money_fmt for c in cost_t.columns[1:]})

    body = "\n".join([
        figure_block(fig["q4_speed"], "fig-q4-speed", "Federal Shipping has the shortest slow tail",
                     f"Share of each carrier's orders shipped within a given number of days "
                     f"({f['shipped_orders']} shipped orders).",
                     share_html, data_label="Show carrier share by year"),
        summary_html,
        figure_block(fig["q4_cost"], "fig-q4-cost", "Federal probably costs a little more for the same orders",
                     "If United charges $100 to ship a set of orders, this is roughly what each other carrier would "
                     "charge for the same orders (same order values, same destination countries).", cost_html,
                     note="Whiskers show the likely range (95% confidence). Estimated with a regression that compares "
                          "orders of the same value shipped to the same country."),
    ])
    finding = (
        f"<p><strong>Federal Shipping is fastest where it matters, in the slow tail.</strong> 90% of its orders shipped "
        f"within {fed['90% shipped within (days)']:.0f} days, against {spd['90% shipped within (days)']:.0f} for "
        f"Speedy Express and {ups['90% shipped within (days)']:.0f} for United Package. Only "
        f"{pct(fed[slow_col], 1)} of Federal's orders took more than two weeks, compared with "
        f"{pct(ups[slow_col], 1)} for United. In a like-for-like comparison (same destination country, similar order "
        f"size, same quarter), Federal ships {-f['adj_days_diff']:.1f} days sooner than United on average and is "
        f"{-f['adj_slow_diff'] * 100:.1f} percentage points less likely to take over two weeks. Both gaps are too "
        f"large to be explained by chance.</p>"
        f"<p>Late rates against the customer's required date are similar across carriers "
        f"({pct(min(x['Late vs required date'] for x in s.values()), 1)}–"
        f"{pct(max(x['Late vs required date'] for x in s.values()), 1)}, a difference small enough to be chance). "
        f"Meanwhile United, the slowest in the tail, <strong>carries the largest and growing "
        f"share</strong> of orders: {pct(f['united_share_first'])} in late 1996, rising to "
        f"{pct(f['united_share_last'])} in 1998.</p>"
        f"<p>On cost, Federal is probably a little more expensive. For the same orders, every $100 of freight with "
        f"United would cost about <strong>${100 * (1 + cost['diff']):.0f}</strong> with Federal. The data can't pin "
        f"this down exactly: the likely range is ${100 * (1 + cost['low']):.0f} to ${100 * (1 + cost['high']):.0f}. "
        "So faster shipping probably comes at a modest premium, which makes this a real trade-off.</p>"
    )
    implications = [
        f"<strong>Move time-sensitive and high-value orders from United to Federal.</strong> Even moving all "
        f"{f['united_ttm_orders']} United orders from the last 12 months would add only about "
        f"{money_k(f['switch_cost_point'])} in "
        f"freight (up to {money_k(f['switch_cost_high'])} at the top of the likely range). That's about "
        f"{pct(f['switch_cost_share_of_revenue'], 1)} of revenue, and it would avoid roughly "
        f"{f['slow_orders_avoided']:.0f} orders a year taking over two weeks.",
        "<strong>Use the volume as leverage.</strong> Before moving it, ask United to commit to a two-week shipping "
        "standard or lower rates. Its share is growing, so Northwind has more volume to bargain with each year.",
        f"<strong>The switch is low-friction.</strong> Customers already receive orders from a median of "
        f"{f['customers_median_shippers']:.0f} different carriers, so changing the mix needs no customer-facing change.",
        "<strong>Start recording delivery dates.</strong> This analysis measures time to shipment, which may partly "
        "reflect warehouse and pickup timing. Delivery dates would show the carriers' true transit performance.",
    ]
    approach = [
        f"Took the {f['shipped_orders']} orders that have shipped and measured <strong>how many days each carrier "
        "took from order to shipment</strong>: the typical time, the time by which 90% of orders had shipped, and the "
        "share that took over two weeks.",
        "Checked with standard statistical tests that the gaps aren't just luck. Then made a <strong>like-for-like "
        "comparison</strong> of orders of similar size, going to the same country, in the same quarter, so a carrier "
        "can't look faster just because it gets easier routes.",
        "Compared <strong>freight cost</strong> the same like-for-like way: orders of the same value going to the "
        "same country.",
        "Limitation: the data records when an order shipped, not when it arrived.",
    ]
    why = (f"Every order depends on a carrier, and freight cost {money_k(f['total_freight'])} over the period. If one "
           "carrier is reliably faster at a similar cost, shifting volume improves the customer experience. Being "
           "able to move volume is also a negotiating lever with the others.")
    return section("shippers", 4, "Which shipper should get more of our volume, weighing speed against cost?",
                   why, approach, body, finding, implications)


def takeaways(results):
    """Build the four headline cards shown under the page title.

    Args:
        results (dict[str, dict]): Each question's ``run`` output,
            keyed ``"q1"`` to ``"q4"``.

    Returns:
        str: HTML ``<div>`` with one card per question.
    """
    f1, f2, f3, f4 = (results[k]["facts"] for k in ("q1", "q2", "q3", "q4"))
    slow_col = "Share taking over {} days".format(f4["slow_days"])
    fed_slow = f4["summary"]["Federal Shipping"][slow_col]
    united_slow = f4["summary"]["United Package"][slow_col]
    cards = [
        ("Growth from existing customers", pct(f1["existing_share"]),
         f"of the revenue increase ({pct(f1['company_growth'], signed=True)}) came from existing customers ordering "
         "more often."),
        ("Suppliers to negotiate with", money_k(f2["negotiate_total"]),
         f"in annual sales from {num(len(f2['negotiate_names']))} large, replaceable suppliers: the case for volume "
         "discounts."),
        ("Customers to call", str(f3["at_risk_count"]),
         f"regular customers are well past their usual reorder time ({money_k(f3['at_risk_revenue'])} a year)."),
        ("Slow shipments with Federal", pct(fed_slow, 1),
         f"of Federal orders took over two weeks, vs {pct(united_slow, 1)} for United."),
    ]
    items = "".join(
        f'<div class="takeaway"><p class="label">{esc(label)}</p><p class="value">{esc(value)}</p><p>{esc(text)}</p></div>'
        for label, value, text in cards
    )
    return f'<div class="takeaways">{items}</div>'


def build(results, dataset, repo_url, generated_on):
    """Assemble the complete HTML page.

    Args:
        results (dict[str, dict]): Each question's ``run`` output,
            keyed ``"q1"`` to ``"q4"``.
        dataset (dict[str, object]): Dataset summary from
            ``run_analysis.dataset_facts``.
        repo_url (str): Public GitHub URL linked in the methods notes.
        generated_on (str): Build date shown in the footer.

    Returns:
        str: Full HTML document; plotly.js is loaded from the CDN.
    """
    q = {k: results[k] for k in ("q1", "q2", "q3", "q4")}
    d = dataset
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Northwind Business Review</title>
<meta name="description" content="Four business questions about Northwind Traders, answered from its order data (Jul 1996 - May 1998).">
<script src="{style.PLOTLY_JS_URL}"></script>
<style>{CSS}</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <p class="eyebrow">15.561 HW 3 · Northwind Traders · {d['orders']} orders, {d['first_date']} – {d['last_date']}</p>
    <h1>Where Northwind should focus next</h1>
    <p class="lede">A review for the general manager covering four questions: where growth comes from, which suppliers
    to negotiate with, which customers are drifting away, and which carrier deserves more volume.</p>
    {takeaways(q)}
  </div>
</header>
<nav class="toc" aria-label="Questions">
  <div class="wrap">
    <a href="#growth">1 · Growth</a>
    <a href="#suppliers">2 · Suppliers</a>
    <a href="#customers">3 · Customers at risk</a>
    <a href="#shippers">4 · Shippers</a>
    <a href="#methods">Data &amp; methods</a>
  </div>
</nav>
<main class="wrap">
{q1_section(q["q1"])}
{q2_section(q["q2"], q["q1"]["facts"], d)}
{q3_section(q["q3"])}
{q4_section(q["q4"])}
<section class="question methods" id="methods">
  <p class="qnum">DATA &amp; METHODS</p>
  <h2>How the numbers were produced</h2>
  <ul>
    <li><strong>Data:</strong> the course's Northwind workbook: {d['orders']} orders, {d['lines']:,} order lines,
    {d['customers']} customers, {d['products']} products, {d['suppliers']} suppliers, {d['employees']} employees and
    {d['shippers']} shippers. Orders run from {d['first_date_long']} to {d['last_date_long']}.</li>
    <li><strong>Revenue</strong> = unit price × quantity × (1 − discount), using the price on each order
    line, which differs from the current list price on {pct(d['price_differs_share'])} of lines. Discounts were rounded
    to two decimals to remove floating-point noise.</li>
    <li><strong>Cleaning:</strong> six columns left in the Product sheet by an earlier exercise were dropped
    (Cheap, NewPrice, Cheap.1, IsCheap, Unnamed: 14, NewPrice.1). No rows were removed.</li>
    <li><strong>Time windows:</strong> growth compares Jan–Apr 1997 with Jan–Apr 1998. Supplier volume uses
    May 1997–Apr 1998. Customer recency is measured as of 6 May 1998.</li>
    <li><strong>Limitations:</strong> there's no purchase-cost data, so profit can't be measured and sales stand in
    for purchase volume. Inventory is a single snapshot. Shipping is measured to the shipment date, not delivery.
    About 22 months of history is too short to estimate seasonality.</li>
    <li><strong>Reproduce:</strong> all figures, tables and numbers on this page are generated by the Python code at
    <a href="{esc(repo_url)}">{esc(repo_url)}</a>. Run <code>python run_analysis.py</code>.</li>
  </ul>
</section>
</main>
<footer>
  <div class="wrap">Generated {esc(generated_on)} from <code>data/Northwind Database.xlsx</code>. Charts are interactive:
  hover for values, or open "Show the data" for the underlying tables.</div>
</footer>
</body>
</html>
"""
