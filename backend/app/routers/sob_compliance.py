"""SOB Compliance dashboard. Same template shape as consumption.py."""

from fastapi import APIRouter, Depends

from app import metrics
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["sob"])


@router.get("/sob-compliance", response_model=DashboardResponse)
def sob_compliance_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    df = apply(store.purchase, f, date_col="PO_Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No purchases recorded for the selected filters."],
            row_count=0,
        )

    # Targets are the FROZEN synthetic commitments. Actual share is recomputed
    # on the filtered data; the target itself never moves.
    comp = metrics.sob_compliance(df, store.sob_targets)

    if not len(comp):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No items with an agreed vendor commitment in this period."],
            row_count=0,
        )

    on_target = int(comp["on_target"].sum())
    off_target = len(comp) - on_target
    compliance_pct = metrics.safe_pct(on_target, len(comp))
    at_risk = float(comp.loc[~comp["on_target"], "Value"].sum())

    kpis = [
        Kpi(label="SOB Compliance", value=compliance_pct,
            display=pct(compliance_pct),
            tone="positive" if compliance_pct >= 70 else "risk"),
        Kpi(label="Items On Target", value=on_target,
            display=qty_compact(on_target), tone="positive"),
        Kpi(label="Items Off Target", value=off_target,
            display=qty_compact(off_target), tone="risk"),
        Kpi(label="Value at Risk", value=at_risk,
            display=inr_compact(at_risk), tone="risk"),
    ]

    names = df[["Item_ID", "Item_Name"]].drop_duplicates()
    vnames = df[["Vendor_ID", "Vendor_Name"]].drop_duplicates()
    comp = comp.merge(names, on="Item_ID").merge(vnames, on="Vendor_ID")

    charts = []

    # THE core visual: target vs actual, side by side, worst variance first.
    worst = comp.sort_values("variance_pct").head(15)
    charts.append(Chart(
        id="target_vs_actual", title="Target vs Actual SOB % by Item",
        type="grouped_bar", x_key="label",
        series=[
            ChartSeries(name="Target %", data=[
                {"label": r["Item_Name"], "value": float(r["target_pct"])}
                for _, r in worst.iterrows()]),
            ChartSeries(name="Actual %", data=[
                {"label": r["Item_Name"], "value": float(r["actual_pct"])}
                for _, r in worst.iterrows()]),
        ],
    ))

    # Compliance trend: recompute month by month on that month's purchases.
    rows = []
    for month, grp in df.groupby("Month_Start"):
        c = metrics.sob_compliance(grp, store.sob_targets)
        if len(c):
            rows.append({
                "month": month.strftime("%b %y"),
                "value": metrics.safe_pct(int(c["on_target"].sum()), len(c)),
            })
    charts.append(Chart(
        id="compliance_trend", title="SOB Compliance % by Month", type="line",
        x_key="month",
        series=[ChartSeries(name="Compliance %", data=rows)],
    ))

    risk = comp[~comp["on_target"]].sort_values("Value", ascending=False).head(10)
    charts.append(Chart(
        id="value_at_risk", title="Off-Target Items Ranked by Value at Risk",
        type="hbar", x_key="label",
        series=[ChartSeries(name="Value at Risk", data=[
            {"label": r["Item_Name"], "value": float(r["Value"])}
            for _, r in risk.iterrows()])],
    ))

    detail = comp.sort_values("variance_pct")
    table = Table(
        columns=[
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "Vendor_Name", "label": "Designated Vendor", "type": "text"},
            {"key": "target_pct", "label": "Target %", "type": "percent"},
            {"key": "actual_pct", "label": "Actual %", "type": "percent"},
            {"key": "variance_pct", "label": "Variance", "type": "percent"},
            {"key": "Value", "label": "Purchase Value", "type": "currency"},
            {"key": "status", "label": "Status", "type": "text"},
        ],
        rows=[{
            "Item_Name": r["Item_Name"], "Vendor_Name": r["Vendor_Name"],
            "target_pct": float(r["target_pct"]),
            "actual_pct": float(r["actual_pct"]),
            "variance_pct": float(r["variance_pct"]),
            "Value": float(r["Value"]),
            "status": "On Target" if r["on_target"] else "Off Target",
        } for _, r in detail.iterrows()],
    )

    insights = [
        f"{compliance_pct}% of tracked items are meeting their agreed vendor share.",
        f"{inr_compact(at_risk)} of purchase value is currently off target.",
    ]

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )
