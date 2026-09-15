"""
SOB Opportunities dashboard.

Where preferred-brand share is being lost, and who is losing it. The lever
here is a conversation with a prescriber, so the breakdowns are by doctor and
by generic rather than by supplier.
"""

from fastapi import APIRouter, Depends

from app import metrics
from app.config import SOB_COMPLIANT_TIERS, TIER_LABELS
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
    df = apply(store.consumption, f, date_col="Date")

    if not len(df):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No consumption recorded for the selected filters."],
            row_count=0,
        )

    total = metrics.total_value(df)
    opp = metrics.sob_opportunity(df, store.preferred_molecules, SOB_COMPLIANT_TIERS)

    if not len(opp):
        return DashboardResponse(
            filters=f.as_dict(), kpis=[], charts=[],
            table=Table(columns=[], rows=[]),
            insights=["No switchable prescribing found for these filters."],
            row_count=0,
        )

    opp_value = metrics.total_value(opp)
    pkg = metrics.total_value(opp[opp["Is_Package"] == True])   # noqa: E712

    # Adherence per prescriber - the number that makes this list actionable.
    adherence = df.groupby("Doctor", as_index=False).apply(
        lambda g: metrics.safe_pct(
            g.loc[g["Formulary_Tier"].isin(SOB_COMPLIANT_TIERS), "Value"].sum(),
            g["Value"].sum()),
        include_groups=False)
    adherence.columns = ["Doctor", "adherence_pct"]
    below = int((adherence["adherence_pct"] < 70).sum())

    kpis = [
        Kpi(label="Total Opportunity", value=opp_value,
            display=inr_compact(opp_value), tone="risk",
            note="Non-preferred spend with a preferred alternative"),
        Kpi(label="% of Consumption", value=metrics.safe_pct(opp_value, total),
            display=pct(metrics.safe_pct(opp_value, total)), tone="risk"),
        Kpi(label="Package Opportunity", value=pkg, display=inr_compact(pkg),
            tone="risk", note="Bundled cases - hospital absorbs the difference"),
        Kpi(label="Non-Package Opportunity", value=opp_value - pkg,
            display=inr_compact(opp_value - pkg)),
        Kpi(label="Doctors Below 70%", value=below, display=qty_compact(below),
            tone="risk", note="Preferred-brand adherence under 70%"),
    ]

    charts = []

    charts.append(Chart(
        id="package_split", title="Package vs Non-Package Opportunity",
        type="donut", x_key="label",
        series=[ChartSeries(name="Opportunity", data=[
            {"label": "Package", "value": float(pkg)},
            {"label": "Non-Package", "value": float(opp_value - pkg)},
        ])],
        drilldown=metrics.items_by_package_split(opp),
    ))

    by_doc = metrics.breakdown(opp, "Doctor", top_n=10)
    charts.append(Chart(
        id="by_doctor", title="Top 10 Doctors by Opportunity", type="hbar",
        x_key="label",
        series=[ChartSeries(name="Opportunity", data=[
            {"label": r["Doctor"], "value": float(r["Value"])}
            for _, r in by_doc.iterrows()])],
            drilldown=metrics.molecule_by_doctor(opp),
    ))

    by_mol = metrics.breakdown(opp, "Molecule", top_n=10)
    charts.append(Chart(
        id="by_molecule", title="Top 10 Generics by Opportunity", type="bar",
        x_key="label",
        series=[ChartSeries(name="Opportunity", data=[
            {"label": r["Molecule"], "value": float(r["Value"])}
            for _, r in by_mol.iterrows()])],
            drilldown=metrics.doctor_brand_by_molecule(opp),
    ))

    by_item = metrics.breakdown(opp, "Item_Name", top_n=10)
    charts.append(Chart(
        id="by_item", title="Top 10 Brands by Opportunity", type="hbar",
        x_key="label",
        series=[ChartSeries(name="Opportunity", data=[
            {"label": r["Item_Name"], "value": float(r["Value"])}
            for _, r in by_item.iterrows()])],
            drilldown=metrics.doctors_by_brand(opp),
    ))

    # Item-level detail, naming the preferred brand that could replace each.
    agg = (opp.groupby(["Molecule", "Item_Name", "Formulary_Tier"], as_index=False)
              ["Value"].sum().sort_values("Value", ascending=False))
    table = Table(
        columns=[
            {"key": "Molecule", "label": "Molecule", "type": "text"},
            {"key": "Item_Name", "label": "Brand Used", "type": "text"},
            {"key": "tier", "label": "Tier", "type": "text"},
            {"key": "alternative", "label": "Preferred Alternative", "type": "text"},
            {"key": "Value", "label": "Opportunity", "type": "currency"},
        ],
        rows=[{
            "Molecule": r["Molecule"], "Item_Name": r["Item_Name"],
            "tier": f"{r['Formulary_Tier']} - {TIER_LABELS.get(r['Formulary_Tier'], '')}",
            "alternative": ", ".join(
                store.preferred_by_molecule.get(r["Molecule"], [])[:2]) or "-",
            "Value": float(r["Value"]),
        } for _, r in agg.iterrows()],
    )

    worst = adherence.sort_values("adherence_pct").iloc[0]
    insights = [
        f"{inr_compact(opp_value)} of prescribing "
        f"({metrics.safe_pct(opp_value, total)}% of consumption) could move to "
        f"a preferred brand in the same molecule.",
        f"{inr_compact(pkg)} of that sits on packaged cases, where the "
        f"hospital absorbs the price difference directly.",
        f"{worst['Doctor']} has the lowest preferred-brand adherence at "
        f"{worst['adherence_pct']:.0f}%; {below} of {len(adherence)} "
        f"prescribers are below 70%.",
    ]
    if len(by_mol):
        t = by_mol.iloc[0]
        insights.append(
            f"{t['Molecule']} is the largest single opportunity at "
            f"{inr_compact(t['Value'])}.")

    return DashboardResponse(
        filters=f.as_dict(), kpis=kpis, charts=charts, table=table,
        insights=insights, row_count=len(opp),
    )