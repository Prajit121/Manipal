"""
Formulary Compliance dashboard.

Matches the client's page structure: overall trend, IP vs OP split, and a
Package/Non-Package split. The client's fourth chart used a specific 4-line
tier legend (S1/I x Package/Non-Package) that was not legible in the source
screenshot - this reconstructs the same STORY (formulary adherence differs
sharply by package status) using our own on/off-formulary flag rather than
guessing at tier labels we could not confirm. Flagged as an approximation,
not a pixel match, in the insights below.
"""

from fastapi import APIRouter, Depends

from app import metrics
from app.config import FORMULARY_TARGET_PCT
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct, qty_compact
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["formulary"])

SEGMENTS = [
    ("On-Formulary", "Package"), ("On-Formulary", "Non-Package"),
    ("Off-Formulary", "Package"), ("Off-Formulary", "Non-Package"),
]


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

    # 1. Month wise Formulary Compliance.
    trend = []
    for month, grp in df.groupby("Month_Start"):
        trend.append({
            "month": month.strftime("%b %y"),
            "value": metrics.safe_pct(
                grp.loc[grp["Is_Formulary"] == True, "Value"].sum(),  # noqa: E712
                grp["Value"].sum()),
        })
    charts.append(Chart(
        id="compliance_trend", title="Month wise Formulary Compliance",
        type="line", x_key="month", value_format="percent",
        reference_line=FORMULARY_TARGET_PCT,
        series=[ChartSeries(name="Compliance %", data=trend)],
        drilldown=metrics.off_formulary_items_by_month(df),
    ))

    # 2. Pharmacy Compliance - IP vs OP.
    ip_op = []
    for month, grp in df.groupby("Month_Start"):
        row = {"month": month.strftime("%b %y")}
        for pt in ["IP", "OP"]:
            seg = grp[grp["Patient_Type"] == pt]
            row[pt] = metrics.safe_pct(
                seg.loc[seg["Is_Formulary"] == True, "Value"].sum(),  # noqa: E712
                seg["Value"].sum()) if len(seg) else 0.0
        ip_op.append(row)
    charts.append(Chart(
        id="ip_op_compliance", title="Pharmacy Compliance", type="line",
        x_key="month", value_format="percent",
        series=[
            ChartSeries(name="IP Compliance", data=[
                {"month": r["month"], "value": r["IP"]} for r in ip_op]),
            ChartSeries(name="OP Compliance", data=[
                {"month": r["month"], "value": r["OP"]} for r in ip_op]),
        ],
        drilldown=metrics.ip_op_compliance_by_dept(df),
    ))

    # 3. Formulary status x Package status - % of monthly value.
    pkg_rows = []
    for month, grp in df.groupby("Month_Start"):
        tot = grp["Value"].sum()
        row = {"month": month.strftime("%b %y")}
        for status, pkg in SEGMENTS:
            mask = (
                (grp["Is_Formulary"] == (status == "On-Formulary"))
                & (grp["Is_Package"] == (pkg == "Package"))
            )
            row[f"{status} - {pkg}"] = metrics.safe_pct(grp.loc[mask, "Value"].sum(), tot)
        pkg_rows.append(row)
    charts.append(Chart(
        id="formulary_by_package", title="Formulary Compliance by Package Status",
        type="line", x_key="month", value_format="percent",
        series=[
            ChartSeries(name=f"{status} - {pkg}", data=[
                {"month": r["month"], "value": r[f"{status} - {pkg}"]}
                for r in pkg_rows])
            for status, pkg in SEGMENTS
        ],
        drilldown=metrics.formulary_package_mix_by_month(df, SEGMENTS),
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
    ]
    if len(ip_op):
        last = ip_op[-1]
        insights.append(
            f"IP compliance runs at {last['IP']:.1f}% against {last['OP']:.1f}% "
            f"for OP - inpatient prescribing sticks to formulary more closely.")
    insights.append(
        "The Package-status split reconstructs the client's chart using our "
        "own on/off-formulary flag; the original's tier-level legend "
        "(S1/I/P1) was not legible in the source screenshot.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )