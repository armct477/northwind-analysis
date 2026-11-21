"""Chart theme, number formatting and HTML table helpers."""

import html
import math

import pandas as pd
import plotly.offline

# Chart palette (light mode). Categorical slots are used in this fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#b4b2a9"
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

PLOTLY_JS_URL = f"https://cdn.plot.ly/plotly-{plotly.offline.get_plotlyjs_version()}.min.js"


def apply_layout(fig, x_title=None, y_title=None, height=420, legend=True):
    """Apply the shared chart theme to a Plotly figure.

    Args:
        fig (plotly.graph_objects.Figure): Figure to style; modified in
            place.
        x_title (str | None): X-axis title; None for no title.
        y_title (str | None): Y-axis title; None for no title.
        height (int): Figure height in pixels.
        legend (bool): Whether to show the legend.

    Returns:
        plotly.graph_objects.Figure: The same ``fig``, for chaining.
    """
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=24, t=16, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=13, color=INK_SECONDARY),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, size=13, color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    font=dict(color=INK_SECONDARY)),
        barcornerradius=4,
    )
    axis = dict(gridcolor=GRID, gridwidth=1, linecolor=BASELINE, zerolinecolor=BASELINE, zerolinewidth=1,
                tickfont=dict(color=INK_MUTED), title_font=dict(color=INK_SECONDARY), automargin=True)
    fig.update_xaxes(title_text=x_title, **axis)
    fig.update_yaxes(title_text=y_title, **axis)
    return fig


def figure_html(fig, div_id):
    """Render a figure as an HTML fragment without the Plotly library.

    Args:
        fig (plotly.graph_objects.Figure): Figure to render.
        div_id (str): ``id`` for the chart's ``<div>``.

    Returns:
        str: Chart ``<div>`` and its inline script; the page must load
        plotly.js separately (see ``PLOTLY_JS_URL``).
    """
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={"displaylogo": False, "responsive": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]},
    )


def money(value, decimals=0):
    """Format a number as US dollars with thousands separators.

    Args:
        value (float): Amount in USD.
        decimals (int): Digits after the decimal point.

    Returns:
        str: For example ``"$1,555"`` or ``"−$5,223"`` (Unicode minus).
    """
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value):,.{decimals}f}"


def money_k(value):
    """Format a dollar amount in thousands with one decimal.

    Args:
        value (float): Amount in USD.

    Returns:
        str: For example ``"$53.2K"`` or ``"−$9.4K"`` (Unicode minus).
    """
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value) / 1000:,.1f}K"


def money_compact(value):
    """Format a dollar amount as a short axis label.

    Args:
        value (float): Amount in USD.

    Returns:
        str: Shortest form with a K or M suffix, e.g. ``"$50K"``,
        ``"$2.5M"`` or ``"$25"``; Unicode minus for negatives.
    """
    sign = "−" if value < 0 else ""
    size = abs(value)
    if size >= 1e6:
        text = f"{size / 1e6:g}M"
    elif size >= 1e3:
        text = f"{size / 1e3:g}K"
    else:
        text = f"{size:g}"
    return f"{sign}${text}"


def nice_step(span, target=6):
    """Choose a round tick spacing for an axis.

    Args:
        span (float): Distance from the lowest to the highest value;
            must be positive.
        target (int): Approximate number of ticks wanted.

    Returns:
        float: Smallest of 1, 2, 2.5, 5 or 10 times a power of ten that
        is at least ``span / target``.
    """
    raw = span / target
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 2.5, 5, 10):
        if raw <= multiple * magnitude:
            return multiple * magnitude
    return 10 * magnitude


def money_axis(fig, axis, low, high, target=8):
    """Set compact dollar tick labels on one axis of a figure.

    Args:
        fig (plotly.graph_objects.Figure): Figure to update in place.
        axis (str): ``"x"`` for the x-axis; any other value means y.
        low (float): Lowest value the ticks must cover, in USD.
        high (float): Highest value the ticks must cover, in USD.
        target (int): Approximate number of ticks.

    Returns:
        plotly.graph_objects.Figure: The same ``fig``, for chaining.
    """
    # Dollar ticks in the same compact style as the data labels ($50K, -$10K).
    # One extra tick on each side; Plotly hides any that fall outside the drawn range.
    step = nice_step(high - low, target)
    ticks = []
    value = math.floor(low / step) * step - step
    while value <= high + step:
        ticks.append(value)
        value += step
    update = dict(tickvals=ticks, ticktext=[money_compact(t) for t in ticks])
    if axis == "x":
        fig.update_xaxes(**update)
    else:
        fig.update_yaxes(**update)
    return fig


def pct(value, decimals=0, signed=False):
    """Format a fraction as a percentage.

    Args:
        value (float): Fraction, e.g. 0.207 for 20.7%.
        decimals (int): Digits after the decimal point.
        signed (bool): Whether to put ``+`` before positive values.

    Returns:
        str: For example ``"21%"`` or ``"+121%"``; negatives use a
        Unicode minus.
    """
    text = f"{value * 100:+.{decimals}f}%" if signed else f"{value * 100:.{decimals}f}%"
    return text.replace("-", "−")


def table_html(df, formats=None, numeric=None, caption=None):
    """Render a DataFrame as an HTML table.

    Args:
        df (pandas.DataFrame): Rows and columns to show, in order.
        formats (dict[str, Callable] | None): Column name to a function
            that turns a non-missing value into display text.
        numeric (Iterable[str] | None): Columns to right-align; None
            means every numeric-dtype column.
        caption (str | None): Table caption; None for no caption.

    Returns:
        str: ``<table>`` inside a horizontally scrollable ``<div>``.
        Missing values become empty cells; all text is HTML-escaped.
    """
    formats = formats or {}
    numeric = set(numeric or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])])
    head = "".join(
        f'<th class="{"num" if c in numeric else ""}">{html.escape(str(c))}</th>' for c in df.columns
    )
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            value = row[c]
            text = formats[c](value) if c in formats and pd.notna(value) else ("" if pd.isna(value) else str(value))
            cells.append(f'<td class="{"num" if c in numeric else ""}">{html.escape(text)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    cap = f"<caption>{html.escape(caption)}</caption>" if caption else ""
    return f'<div class="table-wrap"><table>{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def bar_height(n_bars, per_bar=34, extra=90):
    """Return a chart height that gives each bar a fixed amount of room.

    Args:
        n_bars (int): Number of bars on the category axis.
        per_bar (int): Pixels per bar.
        extra (int): Pixels for axes, legend and margins.

    Returns:
        int: Height in pixels, at least 220.
    """
    return max(220, n_bars * per_bar + extra)
