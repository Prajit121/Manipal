"""Inventory Analysis dashboard. Same template shape as consumption.py."""

from fastapi import APIRouter, Depends

from app import metrics
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["inventory"])

AGE_ORDER = ["Below 30", "30 - 60", "60 - 90", "Above 90"]


@router.get("/inventory-analysis", response_model=DashboardResponse)
def inventory_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    df = apply(store.inventory, f, date_col="Date")
    # Consumption is the denominator for Inventory Days and the source of the
    # HIS figures, so it is filtered identically.
    cons = apply(store.consumption, f, date_col="Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No stock recorded for the selected filters."],
            row_count=0,
        )

    # STOCK IS A POINT-IN-TIME MEASURE. Summing month-end snapshots across a
    # date range double-counts the same physical stock once per month - the
    # figure it produces is meaningless. Every stock KPI and every stock
    # composition chart is therefore computed "as on" the latest snapshot in
    # range, which is how their report labels it: "Inventory Value (As on)".
    # Only the trend charts look across months.
    as_on = df["Date"].max()
    snap = df[df["Date"] == as_on]

    k = metrics.inventory_kpis(snap)
    h = metrics.his_consumption(cons)

    # --- Inventory Days ----------------------------------------------------
    # Client definition: stock value x days elapsed in month / consumption
    # month-to-date.
    days_series = metrics.inventory_days_series(df, cons)
    latest_days = float(days_series["inventory_days"].iloc[-1]) if len(days_series) else 0.0
    avg_days = float(days_series["inventory_days"].mean()) if len(days_series) else 0.0

    in_transit = float(snap["In_Transit_Value"].sum())
    essential_value = metrics.total_value(
        snap[snap["Is_Essential"] == True], "Stock_Value")  # noqa: E712

    # Top five mirror the KPIs on their Inventory Analysis page.
    kpis = [
        Kpi(label="Inventory Days", value=latest_days,
            display=f"{latest_days:.0f}",
            note="Stock value x days elapsed / consumption month-to-date"),
        Kpi(label="Inventory Value", value=k["total_stock_value"],
            display=inr_compact(k["total_stock_value"]),
            note=f"As on {as_on.strftime('%d %b %Y')}"),
        Kpi(label="Stock in Transit", value=in_transit,
            display=inr_compact(in_transit),
            note="Ordered, not yet received"),
        Kpi(label="HIS Consumption", value=h["his_cons"],
            display=inr_compact(h["his_cons"])),
        Kpi(label="HIS Non-Implant Cons", value=h["non_implant_cons"],
            display=inr_compact(h["non_implant_cons"]),
            note=f"Excludes {inr_compact(h['implant_cons'])} of implants"),
        # Risk row - red is reserved for these.
        Kpi(label="% Non-Moving", value=k["non_moving_pct"],
            display=pct(k["non_moving_pct"]),
            tone="risk" if k["non_moving_pct"] > 15 else "neutral",
            note="No issue movement in 90 days"),
        Kpi(label="Essential Stock Value", value=essential_value,
            display=inr_compact(essential_value),
            note="Items flagged must-not-stock-out"),
        Kpi(label="Items Near Expiry", value=k["near_expiry_items"],
            display=qty_compact(k["near_expiry_items"]), tone="risk",
            note="Expiring within 90 days"),
        Kpi(label="Items Expired", value=k["expired_items"],
            display=qty_compact(k["expired_items"]), tone="risk"),
        Kpi(label="Expired Value", value=k["expired_value"],
            display=inr_compact(k["expired_value"]), tone="risk"),
    ]

    charts = []

    # 1. Inventory Days trend - one point per stock snapshot.
    if len(days_series):
        charts.append(Chart(
            id="inventory_days_trend", title="Inventory Days Trend", type="line",
            x_key="month",
            series=[ChartSeries(name="Inventory Days", data=[
                {"month": r["Date"].strftime("%b %y"),
                 "value": float(r["inventory_days"])}
                for _, r in days_series.iterrows()])],
        ))

    # 2. Inventory value against consumption - their paired trend chart.
    stock_m = df.groupby("Month_Start", as_index=False)["Stock_Value"].sum()
    cons_m = metrics.monthly_trend(cons)
    if len(stock_m) and len(cons_m):
        s_map = dict(zip(stock_m["Month_Start"], stock_m["Stock_Value"]))
        c_map = dict(zip(cons_m["Month_Start"], cons_m["Value"]))
        months = sorted(set(s_map) | set(c_map))
        charts.append(Chart(
            id="value_vs_consumption",
            title="Inventory Value & HIS Consumption Trend", type="line",
            x_key="month",
            series=[
                ChartSeries(name="Inventory Value", data=[
                    {"month": m.strftime("%b %y"), "value": float(s_map.get(m, 0))}
                    for m in months]),
                ChartSeries(name="HIS Consumption", data=[
                    {"month": m.strftime("%b %y"), "value": float(c_map.get(m, 0))}
                    for m in months]),
            ],
        ))

    # 3. Ageing - fixed bucket order, not value-sorted.
    age = snap.groupby("Ageing", as_index=False)["Stock_Value"].sum()
    age["_o"] = age["Ageing"].map({a: i for i, a in enumerate(AGE_ORDER)})
    age = age.sort_values("_o")
    charts.append(Chart(
        id="by_ageing", title="Stock Value by Ageing Bucket", type="bar",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Ageing"], "value": float(r["Stock_Value"])}
            for _, r in age.iterrows()])],
    ))

    # 4. Expiry risk as a percentage of stock value over time.
    exp_rows = []
    for month, grp in df.groupby("Month_Start"):
        tot = grp["Stock_Value"].sum()
        exp_rows.append({
            "month": month.strftime("%b %y"),
            "near": metrics.safe_pct(
                grp.loc[grp["Expiry/Near Expiry"] == "Near Expiry", "Stock_Value"].sum(), tot),
            "expired": metrics.safe_pct(
                grp.loc[grp["Expiry/Near Expiry"] == "Expired", "Stock_Value"].sum(), tot),
        })
    charts.append(Chart(
        id="expiry_risk", title="Expiry Risk Trend (% of stock value)",
        type="line", x_key="month",
        series=[
            ChartSeries(name="Near Expiry %", data=[
                {"month": r["month"], "value": r["near"]} for r in exp_rows]),
            ChartSeries(name="Expired %", data=[
                {"month": r["month"], "value": r["expired"]} for r in exp_rows]),
        ],
    ))

    mv = metrics.breakdown(snap, "Moving/Non Moving", value_col="Stock_Value")
    charts.append(Chart(
        id="moving_split", title="Moving vs Non-Moving Stock Value", type="donut",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Moving/Non Moving"], "value": float(r["Stock_Value"])}
            for _, r in mv.iterrows()])],
    ))

    top = metrics.breakdown(snap, "Item_Name", value_col="Stock_Value", top_n=10)
    charts.append(Chart(
        id="top_items", title="Top 10 Items by Stock Value", type="hbar",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Item_Name"], "value": float(r["Stock_Value"])}
            for _, r in top.iterrows()])],
    ))

    detail = snap[["Item_Name", "Batch_No", "Expiry_Date", "Stock_Qty",
                   "Stock_Value", "Ageing", "Expiry/Near Expiry",
                   "Moving/Non Moving", "Is_Essential"]].copy()
    detail = detail.sort_values("Stock_Value", ascending=False).head(500)
    table = Table(
        columns=[
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "Batch_No", "label": "Batch", "type": "text"},
            {"key": "Expiry_Date", "label": "Expiry", "type": "text"},
            {"key": "Stock_Qty", "label": "Qty", "type": "number"},
            {"key": "Stock_Value", "label": "Stock Value", "type": "currency"},
            {"key": "Ageing", "label": "Ageing", "type": "text"},
            {"key": "essential", "label": "Essential", "type": "text"},
            {"key": "flag", "label": "Status", "type": "text"},
        ],
        rows=[{
            "Item_Name": r["Item_Name"], "Batch_No": r["Batch_No"],
            "Expiry_Date": r["Expiry_Date"].strftime("%d %b %Y"),
            "Stock_Qty": int(r["Stock_Qty"]), "Stock_Value": float(r["Stock_Value"]),
            "Ageing": r["Ageing"],
            "essential": "Yes" if r["Is_Essential"] else "",
            "flag": r["Expiry/Near Expiry"] if isinstance(r["Expiry/Near Expiry"], str)
                    else r["Moving/Non Moving"],
        } for _, r in detail.iterrows()],
    )

    total = k["total_stock_value"]
    insights = [
        f"As on {as_on.strftime('%d %b %Y')}, stock covers {latest_days:.0f} "
        f"days of consumption (average {avg_days:.0f} days over the period).",
    ]
    if len(age):
        old = age.loc[age["Ageing"] == "Above 90", "Stock_Value"].sum()
        insights.append(
            f"{metrics.safe_pct(old, total)}% of stock value has been held "
            f"over 90 days.")
    insights.append(
        f"Non-moving stock accounts for {k['non_moving_pct']}% of total value.")
    if k["expired_value"]:
        insights.append(
            f"{k['expired_items']} batches have expired, carrying "
            f"{inr_compact(k['expired_value'])} in stock value.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )