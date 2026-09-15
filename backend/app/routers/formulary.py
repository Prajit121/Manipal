"""Formulary Compliance dashboard. Same template shape as consumption.py."""

from fastapi import APIRouter, Depends

from app import metrics
from app.config import FORMULARY_TARGET_PCT
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["formulary"])


@router.get("/formulary-compliance", response_model=DashboardResponse)
def formulary_dashboard(
    f: Filters = Depends(get_filters),
    store: DataStore = Depends(get_store),
) -> DashboardResponse:
    df = apply(store.consumption, f, date_col="Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No consumption recorded for the selected filters."],
            row_count=0,
        )

    k = metrics.formulary_kpis(df)
    below = k["compliance_pct"] < FORMULARY_TARGET_PCT

    kpis = [
        Kpi(label="Formulary Compliance", value=k["compliance_pct"],
            display=pct(k["compliance_pct"]),
            tone="risk" if below else "positive"),
        Kpi(label="On-Formulary Value", value=k["on_formulary_value"],
            display=inr_compact(k["on_formulary_value"])),
        Kpi(label="Off-Formulary Value", value=k["off_formulary_value"],
            display=inr_compact(k["off_formulary_value"]), tone="risk"),
        Kpi(label="Off-Formulary Items", value=k["off_formulary_items"],
            display=qty_compact(k["off_formulary_items"]), tone="risk"),
    ]

    charts = []

    # Compliance % by month, with the target as a reference line.
    m = df.groupby("Month_Start", as_index=False).apply(
        lambda g: metrics.safe_pct(
            g.loc[g["Is_Formulary"] == True, "Value"].sum(), g["Value"].sum()),
        include_groups=False,
    )
    m.columns = ["Month_Start", "pct"]
    charts.append(Chart(
        id="compliance_trend", title="Formulary Compliance % by Month",
        type="line", x_key="month", value_format="percent",
        reference_line=FORMULARY_TARGET_PCT,
        series=[ChartSeries(name="Compliance %", data=[
            {"month": r["Month_Start"].strftime("%b %y"), "value": float(r["pct"])}
            for _, r in m.sort_values("Month_Start").iterrows()])],
    ))

    # On vs off formulary value per department - where the leaks sit.
    d = df.groupby(["Dept_Name", "Is_Formulary"], as_index=False)["Value"].sum()
    charts.append(Chart(
        id="by_department", title="On vs Off-Formulary Value by Department",
        type="stacked_bar", x_key="label",
        series=[
            ChartSeries(
                name="On Formulary" if flag else "Off Formulary",
                data=[{"label": r["Dept_Name"], "value": float(r["Value"])}
                      for _, r in grp.iterrows()])
            for flag, grp in d.groupby("Is_Formulary")
        ],
    ))

    off = df[df["Is_Formulary"] == False]
    top_off = metrics.breakdown(off, "Item_Name", top_n=10)
    charts.append(Chart(
        id="top_leaks", title="Top Off-Formulary Items by Value (Compliance Leaks)",
        type="hbar", x_key="label",
        series=[ChartSeries(name="Off-Formulary Value", data=[
            {"label": r["Item_Name"], "value": float(r["Value"])}
            for _, r in top_off.iterrows()])],
    ))

    agg = (df.groupby(["Item_ID", "Item_Name", "Category", "Molecule",
                       "Is_Formulary"], as_index=False)["Value"].sum()
             .sort_values("Value", ascending=False))
    total = k["on_formulary_value"] + k["off_formulary_value"]
    table = Table(
        columns=[
            {"key": "Item_Name", "label": "Item", "type": "text"},
            {"key": "Molecule", "label": "Molecule", "type": "text"},
            {"key": "Category", "label": "Category", "type": "text"},
            {"key": "status", "label": "Formulary Status", "type": "text"},
            {"key": "Value", "label": "Consumption Value", "type": "currency"},
            {"key": "share_pct", "label": "% of Total", "type": "percent"},
        ],
        rows=[{
            "Item_Name": r["Item_Name"], "Molecule": r["Molecule"],
            "Category": r["Category"],
            "status": "On Formulary" if r["Is_Formulary"] else "Off Formulary",
            "Value": float(r["Value"]),
            "share_pct": metrics.safe_pct(r["Value"], total),
        } for _, r in agg.iterrows()],
    )

    insights = [
        f"Compliance is {k['compliance_pct']}% against a "
        f"{FORMULARY_TARGET_PCT}% target - "
        f"{'below' if below else 'above'} target.",
        f"{inr_compact(k['off_formulary_value'])} of spend sits off formulary "
        f"across {k['off_formulary_items']} items.",
    ]
    if len(top_off):
        t = top_off.iloc[0]
        insights.append(
            f"{t['Item_Name']} is the single largest leak at "
            f"{inr_compact(t['Value'])}.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )
