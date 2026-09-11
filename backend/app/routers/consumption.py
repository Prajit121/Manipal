"""
Consumption dashboard endpoint.

This is the TEMPLATE. The other four routers copy this structure:
    1. inject filters + store
    2. apply(...) to the right fact table
    3. call metrics.* for every number - never aggregate inline
    4. assemble kpis / charts / table / insights
    5. return DashboardResponse
"""

from fastapi import APIRouter, Depends

from app import metrics
from app.data_loader import DataStore, get_store
from app.filters import ALL, Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["consumption"])


@router.get("/consumption", response_model=DashboardResponse)
def consumption_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    df = apply(store.consumption, f, date_col="Date")

    # Empty filter combination. Return the envelope with empty collections so
    # the frontend renders its empty state, not a wall of blank charts.
    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No consumption recorded for the selected filters."],
            row_count=0,
        )

    k = metrics.consumption_kpis(df)

    # --- Budget ------------------------------------------------------------
    # Budget is held at month x unit x department grain. It has no Stock Take
    # Group dimension, so when the user filters to Pharmacy or General Store
    # we cannot split the plan to match - showing a full budget against a
    # partial actual would overstate the gap. The BUD line is withheld rather
    # than guessed at.
    budget_available = f.stock_take_group == ALL
    bud_monthly = None
    bk = None
    if budget_available:
        bud_df = apply(store.budget, f, date_col="Date")
        bud_monthly = metrics.budget_by_month(bud_df)
        bud_total = float(bud_monthly["Budget_Value"].sum()) if len(bud_monthly) else 0.0
        if bud_total:
            bk = metrics.budget_kpis(k["total_value"], bud_total)

    kpis = [
        Kpi(label="Total Consumption Value", value=k["total_value"],
            display=inr_compact(k["total_value"])),
        Kpi(label="Total Qty Consumed", value=k["total_qty"],
            display=qty_compact(k["total_qty"])),
        Kpi(label="IP Share", value=k["ip_pct"], display=pct(k["ip_pct"])),
        Kpi(label="OP Share", value=k["op_pct"], display=pct(k["op_pct"])),
        Kpi(label="Avg Value / Transaction", value=k["avg_per_txn"],
            display=inr_compact(k["avg_per_txn"])),
    ]

    if bk:
        # Over budget is the risk case. Under budget is NOT automatically
        # good in a hospital - it can mean stockouts - so under-spend stays
        # neutral rather than green.
        kpis.insert(1, Kpi(
            label="Budget", value=bk["budget_value"],
            display=inr_compact(bk["budget_value"])))
        kpis.insert(2, Kpi(
            label="Budget Utilisation", value=bk["utilisation_pct"],
            display=pct(bk["utilisation_pct"]),
            delta_pct=bk["variance_pct"],
            tone="risk" if bk["utilisation_pct"] > 100 else "neutral"))

    charts = []

    # --- Budget vs Actual - the headline chart on their Consumption page ----
    if bud_monthly is not None and len(bud_monthly):
        act_monthly = metrics.monthly_trend(df)
        bud_map = dict(zip(bud_monthly["Month_Start"], bud_monthly["Budget_Value"]))
        act_map = dict(zip(act_monthly["Month_Start"], act_monthly["Value"]))
        months = sorted(set(act_map) | set(bud_map))
        charts.append(Chart(
            id="bud_vs_act", title="Budget vs Actual Consumption", type="line",
            x_key="month",
            series=[
                ChartSeries(name="Budget", data=[
                    {"month": m.strftime("%b %y"), "value": float(bud_map.get(m, 0))}
                    for m in months]),
                ChartSeries(name="Actual", data=[
                    {"month": m.strftime("%b %y"), "value": float(act_map.get(m, 0))}
                    for m in months]),
            ],
        ))

    yoy = metrics.year_over_year(df)
    charts.append(Chart(
        id="yoy_trend", title="Monthly Consumption Value - 2025 vs 2026",
        type="line", x_key="month",
        series=[ChartSeries(name=str(year), data=rows)
                for year, rows in sorted(yoy.items())],
    ))

    dept = metrics.breakdown(df, "Dept_Name")
    charts.append(Chart(
        id="by_department", title="Consumption Value by Department", type="bar",
        x_key="label",
        series=[ChartSeries(name="Value", data=[
            {"label": r["Dept_Name"], "value": float(r["Value"])}
            for _, r in dept.iterrows()])],
    ))

    spec = metrics.breakdown(df, "Specialty")
    charts.append(Chart(
        id="by_specialty", title="Consumption Value by Doctor Specialty",
        type="donut", x_key="label",
        series=[ChartSeries(name="Value", data=[
            {"label": r["Specialty"], "value": float(r["Value"])}
            for _, r in spec.iterrows()])],
    ))

    ptype = df.groupby(["Month_Start", "Patient_Type"], as_index=False)["Value"].sum()
    charts.append(Chart(
        id="op_ip_split", title="OP vs IP Split Over Time", type="stacked_bar",
        x_key="month",
        series=[
            ChartSeries(name=pt, data=[
                {"month": r["Month_Start"].strftime("%b %Y"), "value": float(r["Value"])}
                for _, r in grp.sort_values("Month_Start").iterrows()])
            for pt, grp in ptype.groupby("Patient_Type")
        ],
    ))

    top_items = metrics.breakdown(df, "Item_Name", top_n=10)
    charts.append(Chart(
        id="top_items", title="Top 10 Items by Consumption Value", type="hbar",
        x_key="label",
        series=[ChartSeries(name="Value", data=[
            {"label": r["Item_Name"], "value": float(r["Value"])}
            for _, r in top_items.iterrows()])],
    ))

    agg = (df.groupby(["Item_ID", "Item_Name", "Category"], as_index=False)
             .agg(Qty=("Qty", "sum"), Value=("Value", "sum"))
             .sort_values("Value", ascending=False))
    total = k["total_value"]
    table = Table(
        columns=[
            {"key": "Item_ID", "label": "Item ID", "type": "text"},
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "Category", "label": "Category", "type": "text"},
            {"key": "Qty", "label": "Qty", "type": "number"},
            {"key": "Value", "label": "Value", "type": "currency"},
            {"key": "share_pct", "label": "% of Total", "type": "percent"},
        ],
        rows=[{
            "Item_ID": r["Item_ID"], "Item_Name": r["Item_Name"],
            "Category": r["Category"], "Qty": int(r["Qty"]),
            "Value": float(r["Value"]),
            "share_pct": metrics.safe_pct(r["Value"], total),
        } for _, r in agg.iterrows()],
    )

    # Insight callouts - computed from filtered data, never hardcoded.
    insights = []
    if len(dept):
        top_dept = dept.iloc[0]
        insights.append(
            f"{top_dept['Dept_Name']} accounts for "
            f"{metrics.safe_pct(top_dept['Value'], total)}% of consumption value "
            f"in this period.")
    if len(top_items):
        insights.append(
            f"The top 10 items represent "
            f"{metrics.safe_pct(top_items['Value'].sum(), total)}% of total value.")
    if bk:
        over = "over" if bk["variance_value"] > 0 else "under"
        insights.insert(0,
            f"Consumption is {abs(bk['variance_pct']):.1f}% {over} budget "
            f"({inr_compact(k['total_value'])} against a plan of "
            f"{inr_compact(bk['budget_value'])}).")
    elif not budget_available:
        insights.append(
            "Budget is planned by department, not by stock take group - "
            "clear the group filter to compare against plan.")

    if yoy.get(2025) and yoy.get(2026):
        v25 = sum(r["value"] for r in yoy[2025])
        v26 = sum(r["value"] for r in yoy[2026])
        if v25:
            insights.append(
                f"2026 consumption is {((v26 / v25) - 1) * 100:+.1f}% versus 2025.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )
