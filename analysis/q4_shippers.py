"""Q4: shipping speed and freight cost by carrier."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.formula.api as smf
from scipy import stats

from . import style
from .data import TTM_WINDOW, in_window

SLOW_DAYS = 14  # an order still not shipped after two weeks counts as slow
SHIPPER_ORDER = ["Speedy Express", "United Package", "Federal Shipping"]
SHIPPER_COLOR = dict(zip(SHIPPER_ORDER, style.SERIES[:3]))


def days_within(days, share):
    """Return the days within which a given share of orders shipped.

    Args:
        days (pandas.Series): Days from order to shipment, one per
            shipped order.
        share (float): Target share, e.g. 0.9 for 90%.

    Returns:
        float: Smallest observed value whose cumulative share of orders
        reaches ``share`` (a whole number of days).
    """
    # Smallest whole number of days within which `share` of orders had shipped.
    return float(np.quantile(days, share, method="inverted_cdf"))


def shipper_summary(nw):
    """Build the carrier scorecard.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: One row per carrier in ``SHIPPER_ORDER``:
        order count and share (all orders); median days to ship, days
        by which 90% shipped, share slower than ``SLOW_DAYS`` and late
        share (shipped orders only); mean freight, median freight to
        order value ratio and total freight (all orders). Shares are
        fractions.
    """
    orders = nw.orders
    shipped = orders[orders["Shipped"]]
    rows = []
    for name in SHIPPER_ORDER:
        all_o = orders[orders["ShipperName"] == name]
        s = shipped[shipped["ShipperName"] == name]
        rows.append({
            "Shipper": name,
            "Orders": len(all_o),
            "Share of orders": len(all_o) / len(orders),
            "Median days to ship": s["DaysToShip"].median(),
            "90% shipped within (days)": days_within(s["DaysToShip"], 0.9),
            f"Share taking over {SLOW_DAYS} days": (s["DaysToShip"] > SLOW_DAYS).mean(),
            "Late vs required date": s["Late"].mean(),
            "Average freight": all_o["Freight"].mean(),
            "Freight as % of order value (median)": (all_o["Freight"] / all_o["OrderValue"]).median(),
            "Total freight": all_o["Freight"].sum(),
        })
    return pd.DataFrame(rows)


def share_by_year(nw):
    """Compute each carrier's share of orders per calendar year.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        pandas.DataFrame: Rows are years labeled with the months
        covered (1996 and 1998 are partial); columns are carriers in
        ``SHIPPER_ORDER``; values are fractions summing to 1 per row.
    """
    orders = nw.orders
    table = pd.crosstab(orders["OrderDate"].dt.year, orders["ShipperName"], normalize="index")[SHIPPER_ORDER]
    table.index = [f"{y} (Jul–Dec)" if y == 1996 else (f"{y} (Jan–6 May)" if y == 1998 else str(y))
                   for y in table.index]
    return table


def speed_tests(nw):
    """Test whether shipping speed differs between carriers.

    Runs Kruskal-Wallis and pairwise Mann-Whitney tests on days to
    ship, chi-square tests on slow and late shares, and OLS models
    with HC1 robust errors that control for destination country, log
    order value and quarter (United Package is the reference).

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        dict[str, object]: ``kruskal_p``; ``pairwise`` p-values keyed
        by carrier pair; ``slow_p`` and ``late_p``; and Federal vs
        United estimates ``adj_days_diff`` (days) and
        ``adj_slow_diff`` (change in probability of taking over
        ``SLOW_DAYS``), each with ``_ci`` (95% interval) and ``_p``.
    """
    shipped = nw.orders[nw.orders["Shipped"]].copy()
    groups = {name: shipped.loc[shipped["ShipperName"] == name, "DaysToShip"] for name in SHIPPER_ORDER}
    kruskal_p = stats.kruskal(*groups.values()).pvalue
    pairwise = {
        (a, b): stats.mannwhitneyu(groups[a], groups[b]).pvalue
        for a, b in [("Federal Shipping", "United Package"), ("Federal Shipping", "Speedy Express"),
                     ("Speedy Express", "United Package")]
    }
    slow = pd.crosstab(shipped["ShipperName"], shipped["DaysToShip"] > SLOW_DAYS)
    slow_p = stats.chi2_contingency(slow.values)[1]
    late = pd.crosstab(shipped["ShipperName"], shipped["Late"])
    late_p = stats.chi2_contingency(late.values)[1]

    # Robustness: same comparison holding destination country, order size and quarter fixed.
    shipped["log_value"] = np.log(shipped["OrderValue"])
    shipped["quarter"] = shipped["OrderDate"].dt.to_period("Q").astype(str)
    shipped["slow"] = (shipped["DaysToShip"] > SLOW_DAYS).astype(float)
    formula = "C(ShipperName, Treatment('United Package')) + C(ShipCountry) + log_value + C(quarter)"
    days_model = smf.ols(f"DaysToShip ~ {formula}", data=shipped).fit(cov_type="HC1")
    slow_model = smf.ols(f"slow ~ {formula}", data=shipped).fit(cov_type="HC1")
    term = "C(ShipperName, Treatment('United Package'))[T.Federal Shipping]"
    return {
        "kruskal_p": kruskal_p,
        "pairwise": pairwise,
        "slow_p": slow_p,
        "late_p": late_p,
        "adj_days_diff": days_model.params[term],
        "adj_days_ci": tuple(days_model.conf_int().loc[term]),
        "adj_days_p": days_model.pvalues[term],
        "adj_slow_diff": slow_model.params[term],
        "adj_slow_ci": tuple(slow_model.conf_int().loc[term]),
        "adj_slow_p": slow_model.pvalues[term],
    }


def cost_model(nw):
    """Estimate each carrier's freight cost relative to United Package.

    Fits OLS of log freight on log order value, carrier and
    destination country, with HC1 robust errors.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        tuple[pandas.DataFrame, float, float]: Per-carrier ``diff``
        (fractional cost difference vs United; 0 for United), ``low``
        and ``high`` 95% bounds and ``p`` (NaN for United); the
        elasticity of freight to order value; and the model R-squared.
    """
    # United Package is the reference: it is the carrier volume would move away from.
    orders = nw.orders[(nw.orders["Freight"] > 0) & (nw.orders["OrderValue"] > 0)].copy()
    orders["log_freight"] = np.log(orders["Freight"])
    orders["log_value"] = np.log(orders["OrderValue"])
    model = smf.ols("log_freight ~ log_value + C(ShipperName, Treatment('United Package')) + C(ShipCountry)",
                    data=orders).fit(cov_type="HC1")
    ci = model.conf_int()
    rows = [{"Shipper": "United Package", "diff": 0.0, "low": np.nan, "high": np.nan, "p": np.nan}]
    for name in ["Speedy Express", "Federal Shipping"]:
        term = f"C(ShipperName, Treatment('United Package'))[T.{name}]"
        rows.append({
            "Shipper": name,
            "diff": np.exp(model.params[term]) - 1,
            "low": np.exp(ci.loc[term, 0]) - 1,
            "high": np.exp(ci.loc[term, 1]) - 1,
            "p": model.pvalues[term],
        })
    return pd.DataFrame(rows), model.params["log_value"], model.rsquared


def ecdf_figure(nw, summary):
    """Plot the share of each carrier's orders shipped within N days.

    Args:
        nw (Northwind): Cleaned tables.
        summary (pandas.DataFrame): Output of :func:`shipper_summary`,
            used to mark each carrier's 90% point.

    Returns:
        plotly.graph_objects.Figure: Step-line chart, one line per
        carrier.
    """
    shipped = nw.orders[nw.orders["Shipped"]]
    max_days = int(shipped["DaysToShip"].max())
    days = np.arange(0, max_days + 1)
    fig = go.Figure()
    fig.add_hline(y=90, line=dict(color=style.BASELINE, width=1))
    fig.add_annotation(x=max_days, y=90, xanchor="right", yanchor="top", showarrow=False,
                       text="90% of orders shipped", font=dict(color=style.INK_MUTED, size=11))
    for name in SHIPPER_ORDER:
        d = np.sort(shipped.loc[shipped["ShipperName"] == name, "DaysToShip"].to_numpy())
        share = np.searchsorted(d, days, side="right") / len(d) * 100
        fig.add_trace(go.Scatter(
            x=days, y=share, mode="lines", name=name, line=dict(color=SHIPPER_COLOR[name], width=2, shape="hv"),
            hovertemplate=name + "<br>%{y:.0f}% shipped within %{x} days<extra></extra>",
        ))
        p90 = summary.loc[summary["Shipper"] == name, "90% shipped within (days)"].iloc[0]
        fig.add_trace(go.Scatter(
            x=[p90], y=[90], mode="markers+text", showlegend=False,
            marker=dict(color=SHIPPER_COLOR[name], size=10, line=dict(color=style.SURFACE, width=2)),
            text=[f"{p90:.0f} days"], textposition="bottom center",
            textfont=dict(color=style.INK_SECONDARY, size=11),
            hovertemplate=name + f": 90% shipped within {p90:.0f} days<extra></extra>",
        ))
    style.apply_layout(fig, x_title="Days from order to shipment", y_title="Share of orders shipped (%)", height=440)
    fig.update_yaxes(ticksuffix="%", range=[0, 101])
    fig.update_xaxes(range=[0, max_days], dtick=5)
    fig.update_layout(margin=dict(t=48), hovermode="x unified")
    return fig


def cost_index(costs):
    """Express carrier costs as dollars per $100 charged by United.

    Args:
        costs (pandas.DataFrame): First element returned by
            :func:`cost_model`.

    Returns:
        pandas.DataFrame: ``Shipper``, ``index`` (estimate), ``low``
        and ``high`` (95% bounds; NaN for United).
    """
    # Express each carrier's estimated cost as "dollars per $100 that United charges for the same orders".
    return pd.DataFrame({
        "Shipper": costs["Shipper"],
        "index": 100 * (1 + costs["diff"]),
        "low": 100 * (1 + costs["low"]),
        "high": 100 * (1 + costs["high"]),
    })


def cost_figure(costs):
    """Plot estimated freight per $100 of United freight, by carrier.

    Args:
        costs (pandas.DataFrame): First element returned by
            :func:`cost_model`.

    Returns:
        plotly.graph_objects.Figure: Horizontal bars with 95% range
        whiskers and a reference line at $100.
    """
    data = cost_index(costs).set_index("Shipper").loc[SHIPPER_ORDER[::-1]].reset_index()
    has_range = data["low"].notna()
    labels = [
        f"${row['index']:.0f}  (likely ${row['low']:.0f}–${row['high']:.0f})" if ok else "$100  (baseline)"
        for (_, row), ok in zip(data.iterrows(), has_range)
    ]
    fig = go.Figure(go.Bar(
        x=data["index"], y=data["Shipper"], orientation="h",
        marker=dict(color=[SHIPPER_COLOR[s] for s in data["Shipper"]]),
        error_x=dict(type="data", symmetric=False,
                     array=(data["high"] - data["index"]).fillna(0), arrayminus=(data["index"] - data["low"]).fillna(0),
                     color=style.INK_SECONDARY, thickness=1.5, width=6),
        customdata=labels,
        hovertemplate="%{y}: %{customdata}<extra></extra>",
    ))
    for (_, row), label in zip(data.iterrows(), labels):
        x_end = row["high"] if pd.notna(row["high"]) else row["index"]
        fig.add_annotation(x=x_end, y=row["Shipper"], xanchor="left", showarrow=False, text=f"  {label}",
                           font=dict(color=style.INK_SECONDARY, size=12))
    fig.add_vline(x=100, line=dict(color=style.BASELINE, width=1))
    style.apply_layout(fig, x_title="Freight for the same orders, if United charges $100 (USD)", height=280,
                       legend=False)
    fig.update_xaxes(tickprefix="$", range=[0, 210], dtick=25)
    fig.update_layout(bargap=0.6)
    return fig


def run(nw):
    """Run the Q4 shipper analysis.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        dict[str, dict]: ``facts`` (numbers quoted on the page),
        ``figures`` (Plotly figures by id) and ``tables`` (DataFrames
        by output file name).
    """
    summary = shipper_summary(nw)
    tests = speed_tests(nw)
    costs, value_elasticity, cost_r2 = cost_model(nw)
    shares = share_by_year(nw)
    customers_shippers = nw.orders.groupby("CustomerID")["ShipperName"].nunique().median()
    s = summary.set_index("Shipper")
    fed = costs.set_index("Shipper").loc["Federal Shipping"]
    ttm = nw.orders[in_window(nw.orders["OrderDate"], TTM_WINDOW)]
    united_ttm_freight = ttm.loc[ttm["ShipperName"] == "United Package", "Freight"].sum()
    united_ttm_orders = int((ttm["ShipperName"] == "United Package").sum())
    ttm_revenue = ttm["OrderValue"].sum()

    facts = {
        "summary": s.to_dict(orient="index"),
        "kruskal_p": tests["kruskal_p"],
        "fed_vs_united_p": tests["pairwise"][("Federal Shipping", "United Package")],
        "fed_vs_speedy_p": tests["pairwise"][("Federal Shipping", "Speedy Express")],
        "speedy_vs_united_p": tests["pairwise"][("Speedy Express", "United Package")],
        "slow_p": tests["slow_p"],
        "late_p": tests["late_p"],
        "adj_days_diff": tests["adj_days_diff"],
        "adj_days_ci": tests["adj_days_ci"],
        "adj_days_p": tests["adj_days_p"],
        "adj_slow_diff": tests["adj_slow_diff"],
        "adj_slow_ci": tests["adj_slow_ci"],
        "adj_slow_p": tests["adj_slow_p"],
        "cost": costs.set_index("Shipper").to_dict(orient="index"),
        "value_elasticity": value_elasticity,
        "cost_r2": cost_r2,
        "united_share_first": shares["United Package"].iloc[0],
        "united_share_last": shares["United Package"].iloc[-1],
        "share_labels": list(shares.index),
        "customers_median_shippers": customers_shippers,
        "total_freight": nw.orders["Freight"].sum(),
        "slow_days": SLOW_DAYS,
        "united_ttm_freight": united_ttm_freight,
        "ttm_revenue": ttm_revenue,
        # Extra freight if every United order of the last 12 months had gone with Federal instead.
        "switch_cost_point": united_ttm_freight * fed["diff"],
        "switch_cost_high": united_ttm_freight * fed["high"],
        "switch_cost_share_of_revenue": united_ttm_freight * fed["diff"] / ttm_revenue,
        "united_ttm_orders": united_ttm_orders,
        "shipped_orders": int(nw.orders["Shipped"].sum()),
        "slow_orders_avoided": -united_ttm_orders * tests["adj_slow_diff"],
    }

    share_table = shares.reset_index().rename(columns={"index": "Period"})
    index = cost_index(costs)
    cost_table = pd.DataFrame({
        "Shipper": costs["Shipper"],
        "Freight for the same orders (United = $100)": index["index"],
        "Likely range low": index["low"],
        "Likely range high": index["high"],
        "Difference vs United Package": costs["diff"],
        "p-value": costs["p"],
    })
    return {
        "facts": facts,
        "figures": {"q4_speed": ecdf_figure(nw, summary), "q4_cost": cost_figure(costs)},
        "tables": {"q4_summary": summary, "q4_share_by_year": share_table, "q4_cost": cost_table},
    }
