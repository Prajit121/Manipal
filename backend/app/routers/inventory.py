"""Inventory Analysis dashboard. Same template shape as consumption.py."""

from fastapi import APIRouter, Depends

from app import metrics
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory-analysis", response_model=DashboardResponse)
def inventory_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    df = apply(store.inventory, f, date_col="Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No stock recorded for the selected filters."],
            row_count=0,
        )

    k = metrics.inventory_kpis(df)

    kpis = [
        Kpi(label="Total Stock Value", value=k["total_stock_value"],
            display=inr_compact(k["total_stock_value"])),
        Kpi(label="Total Stock Qty", value=k["total_stock_qty"],
            display=qty_compact(k["total_stock_qty"])),
        Kpi(label="% Non-Moving", value=k["non_moving_pct"],
            display=pct(k["non_moving_pct"]),
            tone="risk" if k["non_moving_pct"] > 15 else "neutral"),
        Kpi(label="Items Near Expiry", value=k["near_expiry_items"],
            display=qty_compact(k["near_expiry_items"]), tone="risk"),
        Kpi(label="Items Expired", value=k["expired_items"],
            display=qty_compact(k["expired_items"]), tone="risk"),
        Kpi(label="Expired Value", value=k["expired_value"],
            display=inr_compact(k["expired_value"]), tone="risk"),
    ]

    charts = []

    # Stock value by ageing bucket - fixed order, not value-sorted.
    AGE_ORDER = ["Below 30", "30 - 60", "60 - 90", "Above 90"]
    age = df.groupby("Ageing", as_index=False)["Stock_Value"].sum()
    age["_o"] = age["Ageing"].map({a: i for i, a in enumerate(AGE_ORDER)})
    age = age.sort_values("_o")
    charts.append(Chart(
        id="by_ageing", title="Stock Value by Ageing Bucket", type="bar",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Ageing"], "value": float(r["Stock_Value"])}
            for _, r in age.iterrows()])],
    ))

    mv = metrics.breakdown(df, "Moving/Non Moving", value_col="Stock_Value")
    charts.append(Chart(
        id="moving_split", title="Moving vs Non-Moving Stock Value", type="donut",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Moving/Non Moving"], "value": float(r["Stock_Value"])}
            for _, r in mv.iterrows()])],
    ))

    yoy = metrics.year_over_year(df, value_col="Stock_Value")
    charts.append(Chart(
        id="stock_trend", title="Stock Value Trend - 2025 vs 2026", type="line",
        x_key="month",
        series=[ChartSeries(name=str(y), data=rows) for y, rows in sorted(yoy.items())],
    ))

    top = metrics.breakdown(df, "Item_Name", value_col="Stock_Value", top_n=10)
    charts.append(Chart(
        id="top_items", title="Top 10 Items by Stock Value", type="hbar",
        x_key="label",
        series=[ChartSeries(name="Stock Value", data=[
            {"label": r["Item_Name"], "value": float(r["Stock_Value"])}
            for _, r in top.iterrows()])],
    ))

    # Batch-level detail. Expired/near-expiry rows carry a flag the frontend
    # uses to tint them - risk colour is driven by data, not hardcoded.
    detail = df[["Item_ID", "Item_Name", "Batch_No", "Expiry_Date", "Stock_Qty",
                 "Stock_Value", "Ageing", "Expiry/Near Expiry",
                 "Moving/Non Moving"]].copy()
    detail = detail.sort_values("Stock_Value", ascending=False).head(500)
    table = Table(
        columns=[
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "Batch_No", "label": "Batch", "type": "text"},
            {"key": "Expiry_Date", "label": "Expiry", "type": "text"},
            {"key": "Stock_Qty", "label": "Qty", "type": "number"},
            {"key": "Stock_Value", "label": "Stock Value", "type": "currency"},
            {"key": "Ageing", "label": "Ageing", "type": "text"},
            {"key": "flag", "label": "Status", "type": "text"},
        ],
        rows=[{
            "Item_Name": r["Item_Name"], "Batch_No": r["Batch_No"],
            "Expiry_Date": r["Expiry_Date"].strftime("%d %b %Y"),
            "Stock_Qty": int(r["Stock_Qty"]), "Stock_Value": float(r["Stock_Value"]),
            "Ageing": r["Ageing"],
            "flag": r["Expiry/Near Expiry"] if isinstance(r["Expiry/Near Expiry"], str)
                    else r["Moving/Non Moving"],
        } for _, r in detail.iterrows()],
    )

    total = k["total_stock_value"]
    insights = []
    if len(age):
        old = age[age["Ageing"] == "Above 90"]["Stock_Value"].sum()
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
