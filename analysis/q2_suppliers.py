"""Q2: supplier dependence and negotiating leverage (last 12 months)."""

import pandas as pd
import plotly.graph_objects as go

from . import style
from .data import TTM_WINDOW, in_window

TTM_LABEL = "May 1997–Apr 1998"
TOP_N = 10                 # suppliers counted as "high volume"
DOMINANCE_THRESHOLD = 0.40  # share of a category above which a supplier is hard to replace

ACTIONS = {
    "negotiate": ("Negotiate volume discount", style.SERIES[0]),
    "protect": ("Protect and line up a second source", style.SERIES[1]),
    "other": ("Smaller supplier", style.NEUTRAL),
}


def ttm_lines(nw):
    """Return the order lines from the last 12 complete months.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: Order lines dated May 1997 to April 1998.
    """
    return nw.lines[in_window(nw.lines["OrderDate"], TTM_WINDOW)]


def category_supply(nw):
    """Split each category's last-12-month sales by product status.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: Indexed by category, with ``total``,
        ``discontinued`` and ``ongoing`` sales in USD,
        ``discontinued_share`` (fraction), and counts of
        ``active_suppliers`` and ``active_products`` (non-discontinued
        products in the Product sheet).
    """
    lines = ttm_lines(nw)
    table = pd.DataFrame({
        "total": lines.groupby("CategoryName")["Revenue"].sum(),
        "discontinued": lines[lines["Discontinued"]].groupby("CategoryName")["Revenue"].sum(),
    }).fillna(0.0)
    table["ongoing"] = table["total"] - table["discontinued"]
    table["discontinued_share"] = table["discontinued"] / table["total"]
    active = nw.products[~nw.products["Discontinued"]]
    table["active_suppliers"] = active.groupby("CategoryName")["SupplierID"].nunique()
    table["active_products"] = active.groupby("CategoryName")["ProductID"].nunique()
    return table


def supplier_leverage(nw):
    """Measure each supplier's volume and how replaceable it is.

    Uses last-12-month sales of non-discontinued products only. A
    supplier's ``category_share`` is its share of each category's
    ongoing sales, weighted by how much of its own sales fall in that
    category. Suppliers with no ongoing sales are omitted.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: One row per supplier, sorted by ``ongoing``
        sales (USD), with ``category_share``, ``main_category``,
        ``discontinued`` sales, ``alternatives`` (other suppliers with
        active products in the main category), ``low_stock_products``
        (active products at or below reorder level),
        ``active_products``, name, country, ``share_of_sales``,
        ``rank`` and ``action`` (``"negotiate"``, ``"protect"`` or
        ``"other"``).
    """
    lines = ttm_lines(nw)
    # Discontinued products will not be bought again, so leverage is measured on ongoing products only.
    ongoing = lines[~lines["Discontinued"]]
    category_total = ongoing.groupby("CategoryName")["Revenue"].sum()

    by_cat = ongoing.groupby(["SupplierID", "CategoryName"])["Revenue"].sum().rename("revenue").reset_index()
    by_cat["category_share"] = by_cat["revenue"] / by_cat["CategoryName"].map(category_total)
    supplier_total = by_cat.groupby("SupplierID")["revenue"].transform("sum")
    by_cat["weight"] = by_cat["revenue"] / supplier_total
    by_cat["weighted_share"] = by_cat["category_share"] * by_cat["weight"]

    main = by_cat.sort_values("revenue", ascending=False).drop_duplicates("SupplierID").set_index("SupplierID")
    table = pd.DataFrame({
        "ongoing": by_cat.groupby("SupplierID")["revenue"].sum(),
        "category_share": by_cat.groupby("SupplierID")["weighted_share"].sum(),
        "main_category": main["CategoryName"],
    })
    table["discontinued"] = lines[lines["Discontinued"]].groupby("SupplierID")["Revenue"].sum()
    table["discontinued"] = table["discontinued"].fillna(0.0)

    products = nw.products
    active = products[~products["Discontinued"]]
    suppliers_per_category = active.groupby("CategoryName")["SupplierID"].nunique()
    table["alternatives"] = table["main_category"].map(suppliers_per_category) - 1
    low_stock = active[active["UnitsInStock"] <= active["ReorderLevel"]]
    table["low_stock_products"] = low_stock.groupby("SupplierID").size()
    table["low_stock_products"] = table["low_stock_products"].fillna(0).astype(int)
    table["active_products"] = active.groupby("SupplierID").size()

    info = nw.suppliers.set_index("SupplierID")[["SupplierName", "SupplierCountry"]]
    table = table.join(info).sort_values("ongoing", ascending=False)
    table["share_of_sales"] = table["ongoing"] / table["ongoing"].sum()
    table["rank"] = range(1, len(table) + 1)

    def action(row):
        """Return the recommended action for one supplier.

        Args:
            row (pandas.Series): Supplier's ``rank`` and
                ``category_share``.

        Returns:
            str: ``"other"`` outside the top ``TOP_N``; otherwise
            ``"protect"`` if ``category_share`` is at least
            ``DOMINANCE_THRESHOLD``, else ``"negotiate"``.
        """
        if row["rank"] > TOP_N:
            return "other"
        return "protect" if row["category_share"] >= DOMINANCE_THRESHOLD else "negotiate"

    table["action"] = table.apply(action, axis=1)
    return table


# Hand-placed label positions so neighbouring suppliers' names don't collide.
LABEL_POSITIONS = {
    "Specialty Biscuits, Ltd.": "middle left",
    "Grandma Kelly's Homestead": "top center",
    "Formaggi Fortini s.r.l.": "middle right",
    "Norske Meierier": "bottom left",
    "Forêts d'érables": "middle right",
    "Pavlova, Ltd.": "bottom center",
    "Pasta Buttini s.r.l.": "middle left",
    "G'day, Mate": "middle right",
    "Gai pâturage": "top center",
    "Aux joyeux ecclésiastiques": "top left",
}


def leverage_figure(table):
    """Plot supplier volume against category share, colored by action.

    Args:
        table (pandas.DataFrame): Output of :func:`supplier_leverage`.

    Returns:
        plotly.graph_objects.Figure: Scatter chart with the top-volume
        and dominance cut-off lines.
    """
    fig = go.Figure()
    for key, (name, color) in ACTIONS.items():
        subset = table[table["action"] == key]
        labels = [n if key != "other" or s >= 0.99 else "" for n, s in zip(subset["SupplierName"], subset["category_share"])]
        positions = [LABEL_POSITIONS.get(n, "top center") for n in subset["SupplierName"]]
        fig.add_trace(go.Scatter(
            x=subset["ongoing"], y=subset["category_share"] * 100, mode="markers+text", name=name,
            marker=dict(color=color, size=11, line=dict(color=style.SURFACE, width=2)),
            text=labels, textposition=positions, textfont=dict(color=style.INK_SECONDARY, size=11),
            customdata=list(zip(subset["SupplierName"], subset["main_category"], subset["alternatives"],
                                subset["SupplierCountry"])),
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[3]})<br>Ongoing sales %{x:$,.0f}<br>"
                           "Share of category %{y:.0f}%<br>Main category %{customdata[1]}<br>"
                           "Other suppliers in category %{customdata[2]}<extra></extra>"),
        ))
    cutoff = table.loc[table["rank"] == TOP_N, "ongoing"].iloc[0]
    fig.add_hline(y=DOMINANCE_THRESHOLD * 100, line=dict(color=style.BASELINE, width=1))
    fig.add_vline(x=cutoff, line=dict(color=style.BASELINE, width=1))
    fig.add_annotation(x=1, xref="paper", y=DOMINANCE_THRESHOLD * 100, yanchor="bottom", xanchor="right",
                       text="Hard to replace above this line", showarrow=False,
                       font=dict(color=style.INK_MUTED, size=11))
    fig.add_annotation(x=cutoff, y=1, yref="paper", xanchor="left", yanchor="top",
                       text=f" Top {TOP_N} by volume →", showarrow=False,
                       font=dict(color=style.INK_MUTED, size=11))
    style.apply_layout(fig, x_title=f"Ongoing sales of the supplier's products, {TTM_LABEL} (USD)",
                       y_title="Supplier's share of its category (%)", height=520)
    fig.update_xaxes(range=[0, table["ongoing"].max() * 1.08])
    style.money_axis(fig, "x", 0, table["ongoing"].max())
    # Start slightly below zero so the 0% and $0 tick labels don't collide at the corner.
    fig.update_yaxes(ticksuffix="%", range=[-5, 108])
    fig.update_layout(margin=dict(t=48))
    return fig


def category_gap_figure(categories):
    """Plot each category's sales split into ongoing and discontinued.

    Args:
        categories (pandas.DataFrame): Output of
            :func:`category_supply`.

    Returns:
        plotly.graph_objects.Figure: Stacked horizontal bar chart,
        labeled where at least 5% of sales are discontinued.
    """
    data = categories.sort_values("discontinued_share")
    fig = go.Figure()
    for column, name, color in [("ongoing", "Products still sold", style.SERIES[0]),
                                ("discontinued", "Products now discontinued", style.SERIES[1])]:
        fig.add_trace(go.Bar(
            x=data[column], y=data.index, orientation="h", name=name, marker=dict(color=color),
            customdata=list(zip(data["discontinued_share"] * 100, data["active_suppliers"])),
            hovertemplate=("%{y}<br>" + name + ": %{x:$,.0f}<br>Discontinued share %{customdata[0]:.0f}%<br>"
                           "Suppliers with active products %{customdata[1]}<extra></extra>"),
        ))
    for category, row in data.iterrows():
        if row["discontinued_share"] >= 0.05:
            fig.add_annotation(x=row["total"], y=category, xanchor="left", showarrow=False,
                               text=f"  {style.pct(row['discontinued_share'])} discontinued",
                               font=dict(color=style.INK_SECONDARY, size=11))
    style.apply_layout(fig, x_title=f"Sales by category, {TTM_LABEL} (USD)",
                       height=style.bar_height(len(data), per_bar=36, extra=110))
    style.money_axis(fig, "x", 0, data["total"].max())
    fig.update_layout(barmode="stack", bargap=0.35, margin=dict(t=48, r=120), legend=dict(traceorder="normal"))
    return fig


def run(nw):
    """Run the Q2 supplier analysis.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        dict[str, dict]: ``facts`` (numbers quoted on the page),
        ``figures`` (Plotly figures by id) and ``tables`` (DataFrames
        by output file name).
    """
    leverage = supplier_leverage(nw)
    categories = category_supply(nw)
    ttm_total = ttm_lines(nw)["Revenue"].sum()
    ongoing_total = leverage["ongoing"].sum()

    negotiate = leverage[leverage["action"] == "negotiate"]
    protect = leverage[leverage["action"] == "protect"]
    top = leverage[leverage["rank"] <= TOP_N]
    meat = categories.loc["Meat/Poultry"]
    meat_suppliers = nw.products[(nw.products["CategoryName"] == "Meat/Poultry") & ~nw.products["Discontinued"]]
    lines = ttm_lines(nw)
    seafood_lines = lines[(lines["CategoryName"] == "Seafood") & ~lines["Discontinued"]]
    seafood_by_supplier = seafood_lines.groupby("SupplierID")["Revenue"].sum()

    facts = {
        "ttm_total": ttm_total,
        "ongoing_total": ongoing_total,
        "discontinued_total": ttm_total - ongoing_total,
        "suppliers": int(len(leverage)),
        "top_n": TOP_N,
        "top_share": top["ongoing"].sum() / ongoing_total,
        "top4_share": leverage.head(4)["ongoing"].sum() / ongoing_total,
        "negotiate_names": negotiate["SupplierName"].tolist(),
        "negotiate_total": negotiate["ongoing"].sum(),
        "negotiate_share": negotiate["ongoing"].sum() / ongoing_total,
        "negotiate_max_share": negotiate["category_share"].max(),
        "protect_names": protect["SupplierName"].tolist(),
        "protect_categories": protect["main_category"].tolist(),
        "protect_shares": protect["category_share"].tolist(),
        "protect_total": protect["ongoing"].sum(),
        "protect_share": protect["ongoing"].sum() / ongoing_total,
        "protect_min_share": protect["category_share"].min(),
        "meat_total": meat["total"],
        "meat_discontinued": meat["discontinued"],
        "meat_discontinued_share": meat["discontinued_share"],
        "meat_active_suppliers": int(meat["active_suppliers"]),
        "meat_active_products": meat_suppliers["ProductName"].tolist(),
        "meat_supplier": meat_suppliers["SupplierName"].iloc[0] if len(meat_suppliers) else "",
        "seafood_suppliers": int(len(seafood_by_supplier)),
        "seafood_total": seafood_by_supplier.sum(),
        "seafood_largest_share": seafood_by_supplier.max() / seafood_by_supplier.sum(),
        "low_stock_top": top[top["low_stock_products"] > 0]["SupplierName"].tolist(),
    }

    table = top.copy()
    table["Action"] = table["action"].map(lambda k: ACTIONS[k][0])
    supplier_table = table[["SupplierName", "SupplierCountry", "main_category", "ongoing", "share_of_sales",
                            "category_share", "alternatives", "low_stock_products", "discontinued", "Action"]]
    supplier_table.columns = ["Supplier", "Country", "Main category", "Ongoing sales", "Share of ongoing sales",
                              "Share of category", "Other suppliers in category", "Products at/below reorder level",
                              "Sales of discontinued products", "Recommended action"]
    full_table = leverage.reset_index()[["rank", "SupplierName", "SupplierCountry", "main_category", "ongoing",
                                         "category_share", "alternatives", "discontinued", "action"]]
    full_table.columns = ["Rank", "Supplier", "Country", "Main category", "Ongoing sales", "Share of category",
                          "Other suppliers in category", "Sales of discontinued products", "Action"]
    category_table = categories.reset_index()[["CategoryName", "ongoing", "discontinued", "discontinued_share",
                                               "active_suppliers", "active_products"]]
    category_table.columns = ["Category", "Products still sold", "Products now discontinued", "Discontinued share",
                              "Suppliers with active products", "Active products"]
    category_table = category_table.sort_values("Discontinued share", ascending=False)

    return {
        "facts": facts,
        "figures": {
            "q2_leverage": leverage_figure(leverage),
            "q2_categories": category_gap_figure(categories),
        },
        "tables": {
            "q2_top_suppliers": supplier_table,
            "q2_all_suppliers": full_table,
            "q2_categories": category_table,
        },
    }
