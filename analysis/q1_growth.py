"""Q1: where revenue growth comes from, Jan-Apr 1997 vs Jan-Apr 1998."""

import pandas as pd
import plotly.graph_objects as go

from . import style
from .data import CURRENT_WINDOW, PRIOR_WINDOW, in_window

PRIOR_LABEL = "Jan–Apr 1997"
CURRENT_LABEL = "Jan–Apr 1998"

STATUS_ORDER = [
    ("grew", "Existing customers buying more"),
    ("shrank", "Existing customers buying less"),
    ("new", "New customers"),
    ("won_back", "Won-back customers"),
    ("lapsed", "Stopped buying (ordered in 1997 window only)"),
]
# Short, line-broken versions for the chart's x-axis.
BRIDGE_AXIS_LABELS = {
    "grew": "Existing:<br>buying more",
    "shrank": "Existing:<br>buying less",
    "new": "New<br>customers",
    "won_back": "Won-back<br>customers",
    "lapsed": "Stopped<br>buying",
}


def window_lines(nw):
    """Split order lines into the two comparison windows.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Order lines dated in
        Jan-Apr 1997, then those dated in Jan-Apr 1998.
    """
    lines = nw.lines
    return (
        lines[in_window(lines["OrderDate"], PRIOR_WINDOW)],
        lines[in_window(lines["OrderDate"], CURRENT_WINDOW)],
    )


def growth_drivers(nw):
    """Compare revenue and its drivers between the two windows.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: Rows are revenue, active customers, orders,
        orders per customer and average order value. Columns are the
        two window labels plus ``Change`` as a fraction (0.21 = +21%).
    """
    orders = nw.orders
    rows = {}
    for label, window in [(PRIOR_LABEL, PRIOR_WINDOW), (CURRENT_LABEL, CURRENT_WINDOW)]:
        o = orders[in_window(orders["OrderDate"], window)]
        customers = o["CustomerID"].nunique()
        rows[label] = {
            "Revenue": o["OrderValue"].sum(),
            "Active customers": customers,
            "Orders": len(o),
            "Orders per customer": len(o) / customers,
            "Average order value": o["OrderValue"].mean(),
        }
    table = pd.DataFrame(rows)
    table["Change"] = table[CURRENT_LABEL] / table[PRIOR_LABEL] - 1
    return table


def customer_bridge(nw):
    """Classify customers by how their revenue changed between windows.

    Classes: ``grew`` and ``shrank`` (bought in both windows), ``new``
    (first ever order after April 1997), ``won_back`` (older customer
    who skipped Jan-Apr 1997) and ``lapsed`` (bought only in 1997).

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Per-customer table
        with ``prior``, ``current``, ``first_order``, ``status`` and
        ``change``; then a summary indexed by class in ``STATUS_ORDER``
        order, with ``customers``, ``change`` and ``label``.
    """
    prior, current = window_lines(nw)
    by_customer = pd.DataFrame({
        "prior": prior.groupby("CustomerID")["Revenue"].sum(),
        "current": current.groupby("CustomerID")["Revenue"].sum(),
    }).fillna(0.0)
    first_order = nw.orders.groupby("CustomerID")["OrderDate"].min()
    by_customer["first_order"] = first_order.reindex(by_customer.index)

    def classify(row):
        """Return the growth class of one customer.

        Args:
            row (pandas.Series): Customer's ``prior`` and ``current``
                revenue and ``first_order`` date.

        Returns:
            str: ``"grew"``, ``"shrank"``, ``"new"``, ``"won_back"`` or
            ``"lapsed"``.
        """
        if row["prior"] > 0 and row["current"] > 0:
            return "grew" if row["current"] >= row["prior"] else "shrank"
        if row["current"] > 0:
            # Did not buy in the prior window: either acquired after it, or an older customer returning.
            return "new" if row["first_order"] >= PRIOR_WINDOW[1] else "won_back"
        return "lapsed"

    by_customer["status"] = by_customer.apply(classify, axis=1)
    by_customer["change"] = by_customer["current"] - by_customer["prior"]
    summary = by_customer.groupby("status").agg(customers=("change", "size"), change=("change", "sum"))
    summary = summary.reindex([key for key, _ in STATUS_ORDER]).fillna(0)
    summary["label"] = [label for _, label in STATUS_ORDER]
    return by_customer, summary


def change_by(nw, column):
    """Compare revenue between the two windows for each group.

    Args:
        nw (Northwind): Cleaned tables.
        column (str): Order-line column to group by, e.g.
            ``"CustomerCountry"`` or ``"ProductName"``.

    Returns:
        pandas.DataFrame: Indexed by group, with ``prior``,
        ``current``, ``change``, ``growth`` (fraction; NaN when prior
        revenue is zero) and ``share_of_growth`` (fraction of the total
        change).
    """
    prior, current = window_lines(nw)
    table = pd.DataFrame({
        "prior": prior.groupby(column)["Revenue"].sum(),
        "current": current.groupby(column)["Revenue"].sum(),
    }).fillna(0.0)
    table["change"] = table["current"] - table["prior"]
    table["growth"] = table["current"] / table["prior"].where(table["prior"] > 0) - 1
    table["share_of_growth"] = table["change"] / table["change"].sum()
    return table


def monthly_revenue(nw):
    """Sum revenue by calendar month, July 1996 to April 1998.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.Series: Revenue in USD indexed by month start. May 1998
        is excluded because it holds only six days of orders.
    """
    lines = nw.lines
    # May 1998 holds only six days of orders, so it is left out of the trend.
    complete = lines[lines["OrderDate"] < CURRENT_WINDOW[1]]
    monthly = complete.groupby(complete["OrderDate"].dt.to_period("M"))["Revenue"].sum()
    monthly.index = monthly.index.to_timestamp()
    return monthly


def monthly_figure(monthly):
    """Plot monthly revenue with the two comparison windows shaded.

    Args:
        monthly (pandas.Series): Output of :func:`monthly_revenue`.

    Returns:
        plotly.graph_objects.Figure: Line chart.
    """
    fig = go.Figure()
    for start, end in [PRIOR_WINDOW, CURRENT_WINDOW]:
        fig.add_vrect(x0=start - pd.Timedelta(days=15), x1=end - pd.Timedelta(days=16),
                      fillcolor=style.SERIES[0], opacity=0.08, line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=monthly.index, y=monthly.values, mode="lines+markers",
        line=dict(color=style.SERIES[0], width=2), marker=dict(size=8, line=dict(color=style.SURFACE, width=2)),
        hovertemplate="%{x|%b %Y}<br>Revenue $%{y:,.0f}<extra></extra>",
    ))
    for (start, _), label in [(PRIOR_WINDOW, PRIOR_LABEL), (CURRENT_WINDOW, CURRENT_LABEL)]:
        fig.add_annotation(x=start + pd.Timedelta(days=45), y=1, yref="paper", yanchor="bottom", text=label,
                           showarrow=False, font=dict(color=style.INK_SECONDARY, size=12))
    style.apply_layout(fig, y_title="Revenue per month (USD)", height=360, legend=False)
    fig.update_yaxes(rangemode="tozero")
    style.money_axis(fig, "y", 0, monthly.max())
    fig.update_layout(margin=dict(t=32))
    return fig


def bridge_figure(summary, prior_total, current_total):
    """Draw the revenue bridge (waterfall) between the two windows.

    Args:
        summary (pandas.DataFrame): Class summary from
            :func:`customer_bridge`.
        prior_total (float): Jan-Apr 1997 revenue in USD.
        current_total (float): Jan-Apr 1998 revenue in USD.

    Returns:
        plotly.graph_objects.Figure: Waterfall chart.
    """
    labels = (["Jan–Apr<br>1997"] + [BRIDGE_AXIS_LABELS[k] for k in summary.index]
              + ["Jan–Apr<br>1998"])
    values = [prior_total] + summary["change"].tolist() + [current_total]
    measures = ["absolute"] + ["relative"] * len(summary) + ["total"]
    customers = ([PRIOR_LABEL] + [f"{label}: {int(n)} customers" for label, n in zip(summary["label"], summary["customers"])]
                 + [CURRENT_LABEL])
    fig = go.Figure(go.Waterfall(
        orientation="v", x=labels, y=values, measure=measures,
        customdata=customers,
        text=[style.money_k(v) for v in values], textposition="outside",
        textfont=dict(color=style.INK_SECONDARY),
        increasing=dict(marker=dict(color=style.SERIES[0])),
        decreasing=dict(marker=dict(color=style.SERIES[7])),
        totals=dict(marker=dict(color=style.INK_MUTED)),
        connector=dict(line=dict(color=style.BASELINE, width=1)),
        hovertemplate="%{customdata}<br>$%{y:,.0f}<extra></extra>",
    ))
    style.apply_layout(fig, y_title="Revenue (USD)", height=440, legend=False)
    fig.update_yaxes(rangemode="tozero")
    running = pd.Series(values[:-1]).cumsum()
    style.money_axis(fig, "y", 0, max(running.max(), current_total))
    fig.update_xaxes(tickangle=0, tickfont=dict(size=12))
    fig.update_layout(bargap=0.45)
    return fig


def country_figure(by_country):
    """Plot the revenue change by customer country as sorted bars.

    Args:
        by_country (pandas.DataFrame): :func:`change_by` output grouped
            by ``CustomerCountry``.

    Returns:
        plotly.graph_objects.Figure: Horizontal bar chart; blue for
        gains, red for losses.
    """
    data = by_country.sort_values("change")
    colors = [style.SERIES[0] if v >= 0 else style.SERIES[7] for v in data["change"]]
    growth_text = ["new market" if pd.isna(g) else style.pct(g, signed=True) for g in data["growth"]]
    fig = go.Figure(go.Bar(
        x=data["change"], y=data.index, orientation="h", marker=dict(color=colors),
        customdata=list(zip(data["prior"], data["current"], growth_text)),
        text=[style.money_k(v) for v in data["change"]], textposition="outside",
        textfont=dict(color=style.INK_SECONDARY, size=11), cliponaxis=False,
        hovertemplate=("%{y}<br>Change %{x:$,.0f}<br>" + PRIOR_LABEL + ": $%{customdata[0]:,.0f}<br>"
                       + CURRENT_LABEL + ": $%{customdata[1]:,.0f}<br>Growth %{customdata[2]}<extra></extra>"),
    ))
    style.apply_layout(fig, x_title=f"Change in revenue, {PRIOR_LABEL} to {CURRENT_LABEL} (USD)",
                       height=style.bar_height(len(data), per_bar=28), legend=False)
    low, high = min(0, data["change"].min()), data["change"].max()
    span = high - low
    # Leave room beyond the bar ends for the outside value labels on both sides.
    fig.update_xaxes(range=[low - 0.15 * span, high + 0.1 * span])
    style.money_axis(fig, "x", low, high)
    fig.update_layout(bargap=0.3, margin=dict(r=56))
    return fig


def category_figure(by_category, company_growth):
    """Plot category growth against the company's overall growth.

    Args:
        by_category (pandas.DataFrame): :func:`change_by` output
            grouped by ``CategoryName``.
        company_growth (float): Company revenue growth as a fraction.

    Returns:
        plotly.graph_objects.Figure: Horizontal bar chart with a
        reference line at ``company_growth``.
    """
    data = by_category.sort_values("growth")
    faster = data["growth"] >= company_growth
    fig = go.Figure()
    for flag, name, color in [(True, "Grew faster than the company", style.SERIES[0]),
                              (False, "Grew slower than the company", style.SERIES[1])]:
        subset = data[faster == flag]
        fig.add_trace(go.Bar(
            x=subset["growth"] * 100, y=subset.index, orientation="h", name=name, marker=dict(color=color),
            customdata=list(zip(subset["prior"], subset["current"], subset["share_of_growth"] * 100)),
            text=[style.pct(g, signed=True) for g in subset["growth"]], textposition="outside",
            textfont=dict(color=style.INK_SECONDARY, size=11), cliponaxis=False,
            hovertemplate=("%{y}<br>Growth %{x:.0f}%<br>" + PRIOR_LABEL + ": $%{customdata[0]:,.0f}<br>"
                           + CURRENT_LABEL + ": $%{customdata[1]:,.0f}<br>"
                           "Share of company growth %{customdata[2]:.0f}%<extra></extra>"),
        ))
    fig.add_vline(x=company_growth * 100, line=dict(color=style.INK_SECONDARY, width=1))
    fig.add_annotation(x=company_growth * 100, y=1, yref="paper", yanchor="bottom", showarrow=False,
                       text=f"Company: {style.pct(company_growth, signed=True)}",
                       font=dict(color=style.INK_SECONDARY, size=12))
    style.apply_layout(fig, x_title=f"Revenue growth, {PRIOR_LABEL} to {CURRENT_LABEL} (%)",
                       height=style.bar_height(len(data), per_bar=34, extra=120))
    fig.update_yaxes(categoryorder="array", categoryarray=list(data.index))
    fig.update_xaxes(ticksuffix="%", rangemode="tozero")
    fig.update_layout(bargap=0.35, barmode="overlay", margin=dict(t=56, r=56),
                      legend=dict(y=1.08))
    return fig


def product_movers(nw, n=5):
    """Find the products whose revenue rose or fell the most.

    Args:
        nw (Northwind): Cleaned tables.
        n (int): Number of products in each list.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]:
        All products (:func:`change_by` columns plus category, supplier
        and ``Discontinued``), the top ``n`` by revenue gain, and the
        top ``n`` by revenue loss.
    """
    by_product = change_by(nw, "ProductName")
    info = nw.products.set_index("ProductName")[["CategoryName", "SupplierName", "Discontinued"]]
    by_product = by_product.join(info)
    gainers = by_product.sort_values("change", ascending=False).head(n)
    decliners = by_product.sort_values("change").head(n)
    return by_product, gainers, decliners


def movers_table(frame):
    """Format a product-movers frame as a display table.

    Args:
        frame (pandas.DataFrame): Gainers or decliners from
            :func:`product_movers`.

    Returns:
        pandas.DataFrame: Product, category, status, revenue in each
        window, change and growth, with display column names.
    """
    table = frame.reset_index().rename(columns={"ProductName": "Product", "CategoryName": "Category"})
    table["Status"] = table["Discontinued"].map({True: "Discontinued", False: "Active"})
    table = table[["Product", "Category", "Status", "prior", "current", "change", "growth"]]
    table.columns = ["Product", "Category", "Status", PRIOR_LABEL, CURRENT_LABEL, "Change", "Growth"]
    return table


def run(nw):
    """Run the Q1 growth analysis.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        dict[str, dict]: ``facts`` (numbers quoted on the page),
        ``figures`` (Plotly figures by id) and ``tables`` (DataFrames
        by output file name).
    """
    prior, current = window_lines(nw)
    prior_total, current_total = prior["Revenue"].sum(), current["Revenue"].sum()
    company_growth = current_total / prior_total - 1

    drivers = growth_drivers(nw)
    by_customer, bridge = customer_bridge(nw)
    by_country = change_by(nw, "CustomerCountry")
    by_category = change_by(nw, "CategoryName")
    by_product, gainers, decliners = product_movers(nw)
    monthly = monthly_revenue(nw)

    existing_net = bridge.loc[["grew", "shrank"], "change"].sum()
    total_change = current_total - prior_total
    top3 = by_country.sort_values("change", ascending=False).head(3)
    declining_countries = by_country[by_country["change"] < 0].sort_values("change")
    top_category = by_category.sort_values("change", ascending=False).iloc[0]
    top_product = gainers.iloc[0]
    discontinued_gainers = gainers[gainers["Discontinued"]]

    facts = {
        "prior_total": prior_total,
        "current_total": current_total,
        "total_change": total_change,
        "company_growth": company_growth,
        "customers_prior": int(drivers.loc["Active customers", PRIOR_LABEL]),
        "customers_current": int(drivers.loc["Active customers", CURRENT_LABEL]),
        "customers_growth": drivers.loc["Active customers", "Change"],
        "orders_per_customer_prior": drivers.loc["Orders per customer", PRIOR_LABEL],
        "orders_per_customer_current": drivers.loc["Orders per customer", CURRENT_LABEL],
        "orders_per_customer_growth": drivers.loc["Orders per customer", "Change"],
        "aov_growth": drivers.loc["Average order value", "Change"],
        "orders_growth": drivers.loc["Orders", "Change"],
        "existing_net": existing_net,
        "existing_share": existing_net / total_change,
        "grew_customers": int(bridge.loc["grew", "customers"]),
        "grew_change": bridge.loc["grew", "change"],
        "new_customers": int(bridge.loc["new", "customers"]),
        "new_change": bridge.loc["new", "change"],
        "won_back_customers": int(bridge.loc["won_back", "customers"]),
        "won_back_change": bridge.loc["won_back", "change"],
        "lapsed_customers": int(bridge.loc["lapsed", "customers"]),
        "lapsed_change": bridge.loc["lapsed", "change"],
        "shrank_customers": int(bridge.loc["shrank", "customers"]),
        "shrank_change": bridge.loc["shrank", "change"],
        "top3_countries": list(top3.index),
        "top3_share": top3["share_of_growth"].sum(),
        "top3_change": top3["change"].tolist(),
        "declining_countries": list(declining_countries.index),
        "declining_change": declining_countries["change"].tolist(),
        "declining_growth": declining_countries["growth"].tolist(),
        "france_growth": by_country.loc["France", "growth"],
        "france_prior": by_country.loc["France", "prior"],
        "faster_categories": by_category[by_category["growth"] >= company_growth].sort_values("growth", ascending=False).index.tolist(),
        "slower_categories": by_category[by_category["growth"] < company_growth].sort_values("growth").index.tolist(),
        "category_growth": by_category["growth"].to_dict(),
        "top_category": top_category.name,
        "top_category_change": top_category["change"],
        "top_category_share": top_category["share_of_growth"],
        "top_product": top_product.name,
        "top_product_change": top_product["change"],
        "top_product_share": top_product["change"] / total_change,
        "discontinued_gainers": discontinued_gainers.index.tolist(),
        "discontinued_gainers_change": discontinued_gainers["change"].tolist(),
        "discontinued_gainers_category": discontinued_gainers["CategoryName"].tolist(),
        "products_declining": int((by_product["change"] < 0).sum()),
        "products_total": int(len(by_product)),
    }

    drivers_table = drivers.reset_index().rename(columns={"index": "Measure"})
    country_table = by_country.sort_values("change", ascending=False).reset_index()
    country_table.columns = ["Country", PRIOR_LABEL, CURRENT_LABEL, "Change", "Growth", "Share of growth"]
    category_table = by_category.sort_values("growth", ascending=False).reset_index()
    category_table.columns = ["Category", PRIOR_LABEL, CURRENT_LABEL, "Change", "Growth", "Share of growth"]
    bridge_table = bridge.reset_index(drop=True)[["label", "customers", "change"]]
    bridge_table.columns = ["Component", "Customers", "Revenue change"]

    return {
        "facts": facts,
        "figures": {
            "q1_monthly": monthly_figure(monthly),
            "q1_bridge": bridge_figure(bridge, prior_total, current_total),
            "q1_country": country_figure(by_country),
            "q1_category": category_figure(by_category, company_growth),
        },
        "tables": {
            "q1_drivers": drivers_table,
            "q1_bridge": bridge_table,
            "q1_country": country_table,
            "q1_category": category_table,
            "q1_gainers": movers_table(gainers),
            "q1_decliners": movers_table(decliners),
            "q1_monthly": monthly.rename("Revenue").rename_axis("Month").reset_index(),
        },
    }
