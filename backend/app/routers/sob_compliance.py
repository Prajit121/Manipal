"""
SOB Compliance dashboard.

Share of Business = the share of prescribing that goes to brands the hospital
has committed volume to. NOT vendor consolidation - this reads Consumption,
not Purchase, because the question is which brand a doctor prescribed within a
molecule, not which supplier the item was bought from.
"""

from fastapi import APIRouter, Depends

from app import metrics
from app.config import FORMULARY_TIERS, SOB_COMPLIANT_TIERS, TIER_LABELS
from app.data_loader import DataStore, get_store
from app.filters import Filters, apply, get_filters
from app.formatting import inr_compact, pct
from app.schemas import Chart, ChartSeries, DashboardResponse, Kpi, Table

router = APIRouter(prefix="/api", tags=["sob"])


def _stacked(df, payers, chart_id, title):
    """100% stacked tier mix per month for a subset of payer types."""
    subset = df[df["Payer_Type"].isin(payers)]
    rows = metrics.sob_tier_by_month(subset, FORMULARY_TIERS)
    if not rows:
        return None
    return Chart(
        id=chart_id, title=title, type="stacked_bar", x_key="month",
        value_format="percent",
        series=[
            ChartSeries(name=f"{t} - {TIER_LABELS[t]}", data=[
                {"month": r["month"], "value": r[t]} for r in rows])
            for t in FORMULARY_TIERS
        ],
    )


@router.get("/sob-compliance", response_model=DashboardResponse)
def sob_compliance_dashboard(
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

    m = metrics.sob_tier_mix(df, SOB_COMPLIANT_TIERS)
    opp = metrics.sob_opportunity(df, store.preferred_molecules, SOB_COMPLIANT_TIERS)
    opp_value = metrics.total_value(opp)

    compliant = "+".join(SOB_COMPLIANT_TIERS)
    kpis = [
        Kpi(label="SOB Compliance", value=m["compliance_pct"],
            display=pct(m["compliance_pct"]),
            tone="positive" if m["compliance_pct"] >= 75 else "risk",
            note=f"Share of value on {compliant} brands"),
        Kpi(label="Preferred Brand Value", value=m["preferred_value"],
            display=inr_compact(m["preferred_value"])),
        Kpi(label="Non-Preferred Value", value=m["non_preferred_value"],
            display=inr_compact(m["non_preferred_value"]), tone="risk"),
        Kpi(label="Switchable Opportunity", value=opp_value,
            display=inr_compact(opp_value), tone="risk",
            note="Where a preferred brand exists for the same molecule"),
    ]

    charts = []
    # Their report splits these two ways because who pays changes the
    # incentive: on scheme and packaged cases the hospital absorbs the drug
    # cost, so brand choice hits margin directly.
    for chart in (
        _stacked(df, ["Scheme"], "mix_scheme", "Scheme / Closed Package - Tier Mix"),
        _stacked(df, ["Cash", "TPA"], "mix_cash_tpa", "Cash / TPA - Tier Mix"),
    ):
        if chart:
            charts.append(chart)

    tier_total = metrics.breakdown(df, "Formulary_Tier")
    charts.append(Chart(
        id="tier_mix", title="Overall Tier Mix", type="donut", x_key="label",
        series=[ChartSeries(name="Value", data=[
            {"label": f"{r['Formulary_Tier']} - {TIER_LABELS.get(r['Formulary_Tier'], '')}",
             "value": float(r["Value"])}
            for _, r in tier_total.iterrows()])],
    ))

    trend = []
    for month, grp in df.groupby("Month_Start"):
        trend.append({
            "month": month.strftime("%b %y"),
            "value": metrics.safe_pct(
                grp.loc[grp["Formulary_Tier"].isin(SOB_COMPLIANT_TIERS), "Value"].sum(),
                grp["Value"].sum()),
        })
    charts.append(Chart(
        id="compliance_trend", title="SOB Compliance % by Month", type="line",
        x_key="month", value_format="percent",
        series=[ChartSeries(name="Compliance %", data=trend)],
    ))

    agg = (df.groupby(["Molecule", "Item_Name", "Formulary_Tier"], as_index=False)
             ["Value"].sum().sort_values("Value", ascending=False))
    table = Table(
        columns=[
            {"key": "Molecule", "label": "Molecule", "type": "text"},
            {"key": "Item_Name", "label": "Brand", "type": "text"},
            {"key": "tier", "label": "Tier", "type": "text"},
            {"key": "Value", "label": "Consumption Value", "type": "currency"},
            {"key": "share_pct", "label": "% of Total", "type": "percent"},
        ],
        rows=[{
            "Molecule": r["Molecule"], "Item_Name": r["Item_Name"],
            "tier": f"{r['Formulary_Tier']} - {TIER_LABELS.get(r['Formulary_Tier'], '')}",
            "Value": float(r["Value"]),
            "share_pct": metrics.safe_pct(r["Value"], m["total"]),
        } for _, r in agg.iterrows()],
    )

    scheme = metrics.sob_tier_mix(df[df["Payer_Type"] == "Scheme"], SOB_COMPLIANT_TIERS)
    cash = metrics.sob_tier_mix(df[df["Payer_Type"] == "Cash"], SOB_COMPLIANT_TIERS)
    insights = [
        f"{m['compliance_pct']}% of consumption value sits on preferred "
        f"({compliant}) brands.",
    ]
    if scheme["total"] and cash["total"]:
        insights.append(
            f"Scheme cases run at {scheme['compliance_pct']}% preferred against "
            f"{cash['compliance_pct']}% on cash - the hospital absorbs drug cost "
            f"on scheme, so the incentive differs.")
    insights.append(
        f"{inr_compact(opp_value)} is switchable: non-preferred prescribing "
        f"where a preferred brand exists for the same molecule.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(df),
    )