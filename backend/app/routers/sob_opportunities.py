"""SOB Opportunities dashboard. Same template shape as consumption.py."""

from fastapi import APIRouter, Depends

from app import metrics
from app.config import SOB_OPPORTUNITY_PCT
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["sob"])


@router.get("/sob-opportunities", response_model=DashboardResponse)
def sob_opportunities_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    # Purchase uses PO_Date - the one per-table variation the filter allows.
    df = apply(store.purchase, f, date_col="PO_Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No purchases recorded for the selected filters."],
            row_count=0,
        )

    total = metrics.total_value(df)
    vendor_spend = metrics.breakdown(df, "Vendor_Name")
    top_share = metrics.safe_pct(vendor_spend.iloc[0]["Value"], total) \
        if len(vendor_spend) else 0.0
    vendors_per_item = df.groupby("Item_ID")["Vendor_ID"].nunique()
    fragmented = int((vendors_per_item >= 3).sum())

    opp = metrics.sob_opportunities(df)
    opp_count = int(opp["is_opportunity"].sum()) if len(opp) else 0

    kpis = [
        Kpi(label="Total Purchase Value", value=total, display=inr_compact(total)),
        Kpi(label="Active Vendors", value=df["Vendor_ID"].nunique(),
            display=str(df["Vendor_ID"].nunique())),
        Kpi(label="Top Vendor Concentration", value=top_share,
            display=pct(top_share)),
        Kpi(label="Items with 3+ Vendors", value=fragmented,
            display=qty_compact(fragmented), tone="risk"),
        Kpi(label="Consolidation Opportunities", value=opp_count,
            display=qty_compact(opp_count), tone="risk"),
    ]

    charts = []

    # Top 5 vendors + Others, so the donut stays readable.
    top5 = vendor_spend.head(5)
    others = vendor_spend.iloc[5:]["Value"].sum() if len(vendor_spend) > 5 else 0
    slices = [{"label": r["Vendor_Name"], "value": float(r["Value"])}
              for _, r in top5.iterrows()]
    if others:
        slices.append({"label": "Others", "value": float(others)})
    charts.append(Chart(
        id="vendor_share", title="Vendor Spend Share", type="donut",
        x_key="label",
        series=[ChartSeries(name="Purchase Value", data=slices)],
    ))

    # THE opportunity list: items split across the most vendors.
    frag = (vendors_per_item.sort_values(ascending=False).head(10)
            .reset_index(name="n_vendors"))
    names = df[["Item_ID", "Item_Name"]].drop_duplicates()
    frag = frag.merge(names, on="Item_ID")
    charts.append(Chart(
        id="fragmentation", title="Most Vendor-Fragmented Items (Opportunity List)",
        type="hbar", x_key="label",
        series=[ChartSeries(name="Distinct Vendors", data=[
            {"label": r["Item_Name"], "value": int(r["n_vendors"])}
            for _, r in frag.iterrows()])],
    ))

    by_month = df.groupby(["Month_Start", "Vendor_Name"], as_index=False)["Value"].sum()
    keep = set(top5["Vendor_Name"])
    by_month = by_month[by_month["Vendor_Name"].isin(keep)]
    charts.append(Chart(
        id="vendor_over_time", title="Purchase Value by Vendor Over Time",
        type="stacked_bar", x_key="month",
        series=[
            ChartSeries(name=v, data=[
                {"month": r["Month_Start"].strftime("%b %y"), "value": float(r["Value"])}
                for _, r in grp.sort_values("Month_Start").iterrows()])
            for v, grp in by_month.groupby("Vendor_Name")
        ],
    ))

    vnames = df[["Vendor_ID", "Vendor_Name"]].drop_duplicates()
    detail = opp.merge(names, on="Item_ID").merge(vnames, on="Vendor_ID")
    item_totals = df.groupby("Item_ID", as_index=False)["Value"].sum() \
                    .rename(columns={"Value": "item_total"})
    detail = detail.merge(item_totals, on="Item_ID")
    detail = detail.merge(
        vendors_per_item.reset_index(name="n_vendors"), on="Item_ID")
    detail = detail.sort_values("item_total", ascending=False)

    table = Table(
        columns=[
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "n_vendors", "label": "# Vendors", "type": "number"},
            {"key": "Vendor_Name", "label": "Top Vendor", "type": "text"},
            {"key": "share_pct", "label": "Top Vendor Share", "type": "percent"},
            {"key": "item_total", "label": "Purchase Value", "type": "currency"},
            {"key": "opportunity", "label": "Assessment", "type": "text"},
        ],
        rows=[{
            "Item_Name": r["Item_Name"], "n_vendors": int(r["n_vendors"]),
            "Vendor_Name": r["Vendor_Name"], "share_pct": float(r["share_pct"]),
            "item_total": float(r["item_total"]),
            "opportunity": "Consolidation opportunity" if r["is_opportunity"]
                           else "Already consolidated",
        } for _, r in detail.iterrows()],
    )

    opp_value = float(detail.loc[detail["is_opportunity"], "item_total"].sum())
    insights = [
        f"{opp_count} of {len(detail)} items have no vendor above "
        f"{SOB_OPPORTUNITY_PCT:.0f}% share - the consolidation shortlist.",
        f"{inr_compact(opp_value)} of spend sits on fragmented items.",
    ]
    if len(vendor_spend):
        insights.append(
            f"{vendor_spend.iloc[0]['Vendor_Name']} is the largest supplier at "
            f"{top_share}% of total spend.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )
