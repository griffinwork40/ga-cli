"""ga_cli — report commands: generic `report` + canned aggregate reports.

All reports are aggregate-only (no user-level / User-Explorer / PII). Every
command builds a RunReportRequest and flattens response rows into a list of
flat dicts (dimension + metric columns) for clean JSON / Rich table output.
"""

from typing import List, Optional

import typer

from ga_cli.app import app
from ga_cli.client import (
    GAError,
    data_client,
    emit,
    get_creds,
    resolve_property,
)

# ---------------------------------------------------------------------------
# Shared report runner
# ---------------------------------------------------------------------------


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_order_by(order_by: Optional[str], metric_names: List[str]):
    """Build a single OrderBy from `--order-by`.

    Syntax: "field" (ascending) or "-field" (descending). If the field is one
    of the requested metrics it becomes a MetricOrderBy, otherwise a
    DimensionOrderBy. Returns a list (empty when unset).
    """
    from google.analytics.data_v1beta.types import OrderBy

    if not order_by:
        return []
    field = order_by.strip()
    desc = field.startswith("-")
    if desc:
        field = field[1:]
    if field in metric_names:
        ob = OrderBy(metric=OrderBy.MetricOrderBy(metric_name=field), desc=desc)
    else:
        ob = OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=field), desc=desc)
    return [ob]


def run_report(
    *,
    property_id: Optional[str],
    metrics: List[str],
    dimensions: Optional[List[str]] = None,
    start: str = "28daysAgo",
    end: str = "today",
    limit: int = 100,
    order_bys=None,
) -> dict:
    """Execute a runReport and flatten rows to a list of flat dicts.

    Builds the RunReportRequest (property/date_ranges/metrics/dimensions),
    runs it, and returns a structured dict with row_count and flat rows.
    """
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )

    if not metrics:
        raise GAError("At least one metric is required (--metrics m1,m2).")

    dimensions = dimensions or []
    creds = get_creds()
    client = data_client(creds)
    pid = resolve_property(property_id)

    req = RunReportRequest(
        property=f"properties/{pid}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[Metric(name=m) for m in metrics],
        dimensions=[Dimension(name=d) for d in dimensions],
        limit=limit,
        order_bys=order_bys or [],
    )
    resp = client.run_report(req)

    dim_headers = [h.name for h in resp.dimension_headers]
    metric_headers = [h.name for h in resp.metric_headers]
    rows = []
    for row in resp.rows:
        rec = {}
        for i, dv in enumerate(row.dimension_values):
            rec[dim_headers[i]] = dv.value
        for i, mv in enumerate(row.metric_values):
            rec[metric_headers[i]] = mv.value
        rows.append(rec)

    return {
        "property_id": pid,
        "date_range": {"start": start, "end": end},
        "dimensions": dim_headers,
        "metrics": metric_headers,
        "row_count": int(getattr(resp, "row_count", len(rows)) or len(rows)),
        "rows": rows,
    }


def _days_start(days: Optional[int], start: str) -> str:
    """`--days N` convenience: sets start to `NdaysAgo` (overrides --start)."""
    if days is not None:
        return f"{days}daysAgo"
    return start


# ---------------------------------------------------------------------------
# Generic report
# ---------------------------------------------------------------------------


@app.command()
def report(
    metrics: str = typer.Option(..., "--metrics", help="Comma-separated metrics, e.g. sessions,totalUsers."),
    dimensions: Optional[str] = typer.Option(None, "--dimensions", help="Comma-separated dimensions."),
    start: str = typer.Option("28daysAgo", "--start", help="Start date (YYYY-MM-DD or NdaysAgo)."),
    end: str = typer.Option("today", "--end", help="End date (YYYY-MM-DD or 'today')."),
    days: Optional[int] = typer.Option(None, "--days", help="Convenience: sets start=NdaysAgo (overrides --start)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(100, "--limit", help="Max rows (default 100)."),
    order_by: Optional[str] = typer.Option(None, "--order-by", help="Order by field; prefix '-' for descending (e.g. -sessions)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table instead of JSON."),
):
    """Generic runReport. Rows are flattened to JSON (dimension + metric columns)."""
    metric_list = _parse_csv(metrics)
    dim_list = _parse_csv(dimensions)
    result = run_report(
        property_id=property_id,
        metrics=metric_list,
        dimensions=dim_list,
        start=_days_start(days, start),
        end=end,
        limit=limit,
        order_bys=_parse_order_by(order_by, metric_list),
    )
    emit(result, pretty, table_title="Report")


# ---------------------------------------------------------------------------
# Canned reports
# ---------------------------------------------------------------------------


@app.command()
def acquisition(
    days: int = typer.Option(28, "--days", help="Trailing window in days (default 28)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(100, "--limit", help="Max rows."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Sessions + users by default channel group."""
    metrics = ["sessions", "totalUsers"]
    result = run_report(
        property_id=property_id,
        metrics=metrics,
        dimensions=["sessionDefaultChannelGroup"],
        start=f"{days}daysAgo",
        end="today",
        limit=limit,
        order_bys=_parse_order_by("-sessions", metrics),
    )
    emit(result, pretty, table_title="Acquisition (channel groups)")


@app.command()
def referrers(
    days: int = typer.Option(28, "--days", help="Trailing window in days (default 28)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(25, "--limit", help="Top N referrers (default 25)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Sessions + users by source / medium (top referrers)."""
    metrics = ["sessions", "totalUsers"]
    result = run_report(
        property_id=property_id,
        metrics=metrics,
        dimensions=["sessionSourceMedium"],
        start=f"{days}daysAgo",
        end="today",
        limit=limit,
        order_bys=_parse_order_by("-sessions", metrics),
    )
    emit(result, pretty, table_title="Referrers (source / medium)")


@app.command("top-pages")
def top_pages(
    days: int = typer.Option(28, "--days", help="Trailing window in days (default 28)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(25, "--limit", help="Top N pages (default 25)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Page views + sessions by page path (+ page title), top N."""
    metrics = ["screenPageViews", "sessions"]
    result = run_report(
        property_id=property_id,
        metrics=metrics,
        dimensions=["pagePath", "pageTitle"],
        start=f"{days}daysAgo",
        end="today",
        limit=limit,
        order_bys=_parse_order_by("-screenPageViews", metrics),
    )
    emit(result, pretty, table_title="Top pages")


@app.command()
def geo(
    days: int = typer.Option(28, "--days", help="Trailing window in days (default 28)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(50, "--limit", help="Top N countries (default 50)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Sessions + users by country."""
    metrics = ["sessions", "totalUsers"]
    result = run_report(
        property_id=property_id,
        metrics=metrics,
        dimensions=["country"],
        start=f"{days}daysAgo",
        end="today",
        limit=limit,
        order_bys=_parse_order_by("-sessions", metrics),
    )
    emit(result, pretty, table_title="Geo (country)")


@app.command()
def trend(
    days: int = typer.Option(28, "--days", help="Trailing window in days (default 28)."),
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    limit: int = typer.Option(400, "--limit", help="Max rows (days)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Sessions + users by date (daily trend), ascending by date."""
    metrics = ["sessions", "totalUsers"]
    result = run_report(
        property_id=property_id,
        metrics=metrics,
        dimensions=["date"],
        start=f"{days}daysAgo",
        end="today",
        limit=limit,
        order_bys=_parse_order_by("date", metrics),
    )
    emit(result, pretty, table_title="Trend (by date)")


@app.command()
def metadata(
    property_id: Optional[str] = typer.Option(None, "--property", help="Property ID (overrides GA_PROPERTY_ID env)."),
    pretty: bool = typer.Option(False, "--pretty", help="Render a Rich table."),
):
    """Dump available dimensions & metrics for the property (getMetadata)."""
    creds = get_creds()
    client = data_client(creds)
    pid = resolve_property(property_id)
    meta = client.get_metadata(name=f"properties/{pid}/metadata")
    dims = [
        {"api_name": d.api_name, "ui_name": d.ui_name, "category": d.category}
        for d in meta.dimensions
    ]
    mets = [
        {
            "api_name": m.api_name,
            "ui_name": m.ui_name,
            "category": m.category,
            "type": m.type_.name if hasattr(m.type_, "name") else str(m.type_),
        }
        for m in meta.metrics
    ]
    result = {
        "property_id": pid,
        "dimension_count": len(dims),
        "metric_count": len(mets),
        "dimensions": dims,
        "metrics": mets,
    }
    if pretty:
        # Two tables are awkward; pretty falls back to the metrics table which
        # is the more common lookup. JSON (default) carries both in full.
        emit({"rows": mets}, pretty=True, table_title=f"Metrics ({len(mets)})")
    else:
        emit(result, pretty=False)
