"""Q3: customers overdue for a reorder, and a back-test of the rule."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from . import style
from .data import CURRENT_WINDOW, PRIOR_WINDOW, in_window

MIN_ORDERS = 3            # need at least two gaps between orders to know a customer's rhythm
AT_RISK_MULTIPLE = 3.0    # days since last order >= 3x the customer's usual gap
WATCH_MULTIPLE = 2.0
# Back-test: apply the rule on the first day of each month and check who orders in the next 120 days.
BACKTEST_CUTOFFS = pd.date_range("1997-07-01", "1998-01-01", freq="MS")
BACKTEST_HORIZON_DAYS = 120

STATUS_STYLE = {
    "At risk": style.STATUS["critical"],
    "Watch": style.STATUS["warning"],
    "On track": style.NEUTRAL,
}


def classify(overdue):
    """Return a customer's risk status from how overdue they are.

    Args:
        overdue (float): Days since last order divided by the usual
            gap between orders.

    Returns:
        str: ``"At risk"`` at ``AT_RISK_MULTIPLE`` or more, ``"Watch"``
        at ``WATCH_MULTIPLE`` or more, otherwise ``"On track"`` (also
        for NaN).
    """
    if overdue >= AT_RISK_MULTIPLE:
        return "At risk"
    if overdue >= WATCH_MULTIPLE:
        return "Watch"
    return "On track"


def customer_cadence(orders, as_of):
    """Summarize each customer's ordering rhythm as of a given date.

    Args:
        orders (pandas.DataFrame): Orders with ``CustomerID``,
            ``CustomerName``, ``CustomerCountry``, ``OrderDate``,
            ``EmployeeID`` and ``OrderValue``; rows after ``as_of``
            are ignored.
        as_of (pandas.Timestamp): Date treated as "today".

    Returns:
        pandas.DataFrame: One row per customer, indexed by
        ``CustomerID``, with order count, first and last order,
        ``usual_gap`` (median days between orders, at least 1; NaN
        with one order), ``days_since``, ``revenue_12m`` (365 days up
        to ``as_of``), ``revenue_lifetime``, ``distinct_reps``,
        ``top_rep_share``, ``overdue`` and ``status``. Customers with
        fewer than ``MIN_ORDERS`` orders get ``"Too little history"``.
    """
    orders = orders[orders["OrderDate"] <= as_of].sort_values("OrderDate")
    year_start = as_of - pd.Timedelta(days=365)
    rows = []
    for customer_id, group in orders.groupby("CustomerID"):
        gaps = group["OrderDate"].diff().dt.days.dropna()
        rep_counts = group["EmployeeID"].value_counts()
        rows.append({
            "CustomerID": customer_id,
            "CustomerName": group["CustomerName"].iloc[0],
            "Country": group["CustomerCountry"].iloc[0],
            "orders": len(group),
            "first_order": group["OrderDate"].min(),
            "last_order": group["OrderDate"].max(),
            # Same-day repeat orders give a zero gap; floor at one day.
            "usual_gap": max(gaps.median(), 1.0) if len(gaps) else np.nan,
            "days_since": (as_of - group["OrderDate"].max()).days,
            "revenue_12m": group.loc[group["OrderDate"] > year_start, "OrderValue"].sum(),
            "revenue_lifetime": group["OrderValue"].sum(),
            "distinct_reps": group["EmployeeID"].nunique(),
            "top_rep_share": rep_counts.iloc[0] / len(group),
        })
    table = pd.DataFrame(rows).set_index("CustomerID")
    table["overdue"] = table["days_since"] / table["usual_gap"]
    enough = table["orders"] >= MIN_ORDERS
    table["status"] = np.where(enough, table["overdue"].apply(classify), "Too little history")
    return table


def backtest(nw):
    """Test the risk rule on past data.

    Applies the rule on each date in ``BACKTEST_CUTOFFS`` using only
    earlier orders, then checks who ordered within
    ``BACKTEST_HORIZON_DAYS``. Snapshots from all cutoffs are pooled.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        tuple[pandas.DataFrame, float, int]: Summary by status (on
        track, watch, at risk) with ``snapshots``, distinct
        ``customers`` and the ``ordered_again`` rate; the Fisher exact
        p-value for at risk vs the rest (indicative only, since one
        customer's snapshots are not independent); and the number of
        pooled snapshots.
    """
    orders = nw.orders
    snapshots = []
    for cutoff in BACKTEST_CUTOFFS:
        cadence = customer_cadence(orders[orders["OrderDate"] < cutoff], cutoff - pd.Timedelta(days=1))
        cadence = cadence[cadence["status"] != "Too little history"].copy()
        horizon = orders[(orders["OrderDate"] >= cutoff)
                         & (orders["OrderDate"] < cutoff + pd.Timedelta(days=BACKTEST_HORIZON_DAYS))]
        cadence["ordered_again"] = cadence.index.isin(horizon["CustomerID"])
        cadence["cutoff"] = cutoff
        snapshots.append(cadence.reset_index())
    pooled = pd.concat(snapshots, ignore_index=True)
    summary = pooled.groupby("status").agg(
        snapshots=("ordered_again", "size"),
        customers=("CustomerID", "nunique"),
        ordered_again=("ordered_again", "mean"),
    ).reindex(["On track", "Watch", "At risk"])
    at_risk = (pooled["status"] == "At risk").to_numpy()
    contingency = pd.crosstab(at_risk, pooled["ordered_again"].to_numpy())
    # Snapshots of the same customer are not independent, so treat this p-value as indicative only.
    p_value = stats.fisher_exact(contingency.values)[1]
    return summary, p_value, len(pooled)


def rep_check(cadence):
    """Test whether rep concentration relates to being overdue.

    Args:
        cadence (pandas.DataFrame): Output of
            :func:`customer_cadence`.

    Returns:
        tuple[float, float, float]: Spearman correlation between
        ``top_rep_share`` and ``overdue``, its p-value, and the median
        number of distinct reps per customer. Customers with too
        little history are excluded.
    """
    eligible = cadence[cadence["status"] != "Too little history"]
    rho, p_value = stats.spearmanr(eligible["top_rep_share"], eligible["overdue"])
    return rho, p_value, eligible["distinct_reps"].median()


def risk_figure(cadence):
    """Plot each customer's usual gap against days since last order.

    Args:
        cadence (pandas.DataFrame): Output of
            :func:`customer_cadence`.

    Returns:
        plotly.graph_objects.Figure: Bubble chart (area = last-12-month
        revenue) with usual-gap, watch and at-risk reference lines.
    """
    data = cadence[cadence["status"] != "Too little history"]
    max_gap = data["usual_gap"].max() * 1.05
    max_since = data["days_since"].max() * 1.1
    fig = go.Figure()
    for multiple, label in [(1, "Usual gap"), (WATCH_MULTIPLE, f"{WATCH_MULTIPLE:g}× (watch)"),
                            (AT_RISK_MULTIPLE, f"{AT_RISK_MULTIPLE:g}× (at risk)")]:
        x_end = min(max_gap, max_since / multiple)
        fig.add_trace(go.Scatter(x=[0, x_end], y=[0, x_end * multiple], mode="lines", hoverinfo="skip",
                                 line=dict(color=style.BASELINE, width=1), showlegend=False))
        fig.add_annotation(x=x_end, y=x_end * multiple, text=label, showarrow=False, xanchor="right",
                           yanchor="bottom", font=dict(color=style.INK_MUTED, size=11))
    size_ref = 2.0 * data["revenue_12m"].max() / (34 ** 2)
    for status in ["On track", "Watch", "At risk"]:
        subset = data[data["status"] == status]
        labels = subset["CustomerName"].where(subset["status"] != "On track", "")
        fig.add_trace(go.Scatter(
            x=subset["usual_gap"], y=subset["days_since"], mode="markers+text", name=status,
            marker=dict(color=STATUS_STYLE[status], size=subset["revenue_12m"].clip(lower=500), sizemode="area",
                        sizeref=size_ref, sizemin=6, line=dict(color=style.SURFACE, width=2),
                        opacity=0.9 if status != "On track" else 0.7),
            text=labels, textposition="middle right", textfont=dict(color=style.INK_SECONDARY, size=11),
            customdata=list(zip(subset["CustomerName"], subset["Country"], subset["orders"],
                                subset["revenue_12m"], subset["overdue"], subset["last_order"].dt.strftime("%d %b %Y"))),
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>Usual gap %{x:.0f} days<br>"
                           "Days since last order %{y}<br>Overdue %{customdata[4]:.1f}× usual gap<br>"
                           "Last order %{customdata[5]}<br>Orders %{customdata[2]}<br>"
                           "Revenue, last 12 months $%{customdata[3]:,.0f}<extra></extra>"),
        ))
    style.apply_layout(fig, x_title="Customer's usual gap between orders (median, days)",
                       y_title="Days since last order (as of 6 May 1998)", height=540)
    fig.update_xaxes(range=[0, max_gap])
    fig.update_yaxes(range=[0, max_since])
    fig.update_layout(margin=dict(t=48, r=24))
    return fig


def run(nw):
    """Run the Q3 at-risk customer analysis.

    Args:
        nw (Northwind): Cleaned tables.

    Returns:
        dict[str, dict]: ``facts`` (numbers quoted on the page),
        ``figures`` (Plotly figures by id) and ``tables`` (DataFrames
        by output file name).
    """
    as_of = nw.as_of
    cadence = customer_cadence(nw.orders, as_of)
    backtest_summary, backtest_p, backtest_n = backtest(nw)
    rho, rho_p, median_reps = rep_check(cadence)

    at_risk = cadence[cadence["status"] == "At risk"].sort_values("revenue_12m", ascending=False)
    watch = cadence[cadence["status"] == "Watch"].sort_values("revenue_12m", ascending=False)
    thin = cadence[cadence["status"] == "Too little history"]
    total_12m = cadence["revenue_12m"].sum()
    eligible = cadence[cadence["status"] != "Too little history"]
    sensitivity = pd.DataFrame([
        {"Threshold (× usual gap)": m,
         "Customers flagged": int((eligible["overdue"] >= m).sum()),
         "Revenue, last 12 months": eligible.loc[eligible["overdue"] >= m, "revenue_12m"].sum()}
        for m in [1.5, 2.0, 3.0, 4.0]
    ])

    never_ordered = sorted(set(nw.customers["CustomerID"]) - set(nw.orders["CustomerID"]))

    # Link to Q1: how the flagged customers' Jan-Apr revenue moved between 1997 and 1998.
    flagged = pd.concat([at_risk, watch])
    orders = nw.orders
    prior_rev = orders[in_window(orders["OrderDate"], PRIOR_WINDOW)].groupby("CustomerID")["OrderValue"].sum()
    current_rev = orders[in_window(orders["OrderDate"], CURRENT_WINDOW)].groupby("CustomerID")["OrderValue"].sum()
    flagged_prior = prior_rev.reindex(flagged.index).fillna(0)
    flagged_current = current_rev.reindex(flagged.index).fillna(0)
    french = flagged["Country"] == "France"

    facts = {
        "as_of": as_of,
        "customers_ordered": int(len(cadence)),
        "eligible": int(len(eligible)),
        "at_risk_count": int(len(at_risk)),
        "at_risk_revenue": at_risk["revenue_12m"].sum(),
        "at_risk_share": at_risk["revenue_12m"].sum() / total_12m,
        "at_risk_lifetime": at_risk["revenue_lifetime"].sum(),
        "top_at_risk": at_risk.head(3)["CustomerName"].tolist(),
        "top_at_risk_revenue": at_risk.head(3)["revenue_12m"].tolist(),
        "top_at_risk_overdue": at_risk.head(3)["overdue"].tolist(),
        "top_at_risk_country": at_risk.head(3)["Country"].tolist(),
        "at_risk_countries": at_risk["Country"].value_counts().to_dict(),
        "watch_count": int(len(watch)),
        "watch_revenue": watch["revenue_12m"].sum(),
        "thin_names": thin["CustomerName"].tolist(),
        "never_ordered": len(never_ordered),
        "watch_names": watch["CustomerName"].tolist(),
        "at_risk_names": at_risk["CustomerName"].tolist(),
        "at_risk_multiple": AT_RISK_MULTIPLE,
        "watch_multiple": WATCH_MULTIPLE,
        "flagged_count": int(len(at_risk) + len(watch)),
        "flagged_revenue": at_risk["revenue_12m"].sum() + watch["revenue_12m"].sum(),
        "flagged_share": (at_risk["revenue_12m"].sum() + watch["revenue_12m"].sum()) / total_12m,
        "flagged_countries": flagged["Country"].value_counts().to_dict(),
        "flagged_prior_window": flagged_prior.sum(),
        "flagged_current_window": flagged_current.sum(),
        "france_flagged": int(french.sum()),
        "france_flagged_prior_window": flagged_prior[french].sum(),
        "france_flagged_current_window": flagged_current[french].sum(),
        "top_at_risk_gap": at_risk.head(3)["usual_gap"].tolist(),
        "top_at_risk_days": at_risk.head(3)["days_since"].tolist(),
        "top_at_risk_lifetime": at_risk.head(3)["revenue_lifetime"].tolist(),
        "backtest_snapshots": backtest_n,
        "backtest_cutoffs": len(BACKTEST_CUTOFFS),
        "backtest_horizon": BACKTEST_HORIZON_DAYS,
        "backtest_on_track_reorder": backtest_summary.loc["On track", "ordered_again"],
        "backtest_watch_reorder": backtest_summary.loc["Watch", "ordered_again"],
        "backtest_at_risk_reorder": backtest_summary.loc["At risk", "ordered_again"],
        "backtest_at_risk_n": int(backtest_summary.loc["At risk", "snapshots"]),
        "backtest_on_track_n": int(backtest_summary.loc["On track", "snapshots"]),
        "backtest_p": backtest_p,
        "rep_rho": rho,
        "rep_p": rho_p,
        "median_reps": median_reps,
    }

    def contact_table(frame):
        """Format customer rows as a display table.

        Args:
            frame (pandas.DataFrame): Rows of
                :func:`customer_cadence` output.

        Returns:
            pandas.DataFrame: Name, country, status, orders, usual gap,
            days since last order, overdue multiple, last order date
            (YYYY-MM-DD) and last-12-month revenue.
        """
        table = frame.reset_index()[["CustomerName", "Country", "status", "orders", "usual_gap", "days_since",
                                     "overdue", "last_order", "revenue_12m"]]
        table["last_order"] = table["last_order"].dt.strftime("%Y-%m-%d")
        table.columns = ["Customer", "Country", "Status", "Orders", "Usual gap (days)", "Days since last order",
                         "Overdue (× usual gap)", "Last order", "Revenue, last 12 months"]
        return table

    backtest_table = backtest_summary.reset_index()
    backtest_table.columns = ["Status at cutoff", "Customer snapshots", "Distinct customers",
                              f"Ordered again within {BACKTEST_HORIZON_DAYS} days"]
    all_customers = contact_table(cadence.sort_values(["status", "overdue"], ascending=[True, False]))

    return {
        "facts": facts,
        "figures": {"q3_risk": risk_figure(cadence)},
        "tables": {
            "q3_contact_list": contact_table(pd.concat([at_risk, watch])),
            "q3_backtest": backtest_table,
            "q3_sensitivity": sensitivity,
            "q3_all_customers": all_customers,
        },
    }
