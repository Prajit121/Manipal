"""
THE filter contract. All endpoints accept exactly these query params and apply
them through exactly this function.

The hierarchy params are what let one web page replace five Power BI tabs.
PRAVAH duplicates every dashboard once per level (Network/Region/Zone/Cluster/
Unit) because Power BI has no clean way to make one page respond to a scope
selector. Here it is four dropdowns on a shared filter bar.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
from fastapi import Query

from app.config import AS_OF_DATE, DATA_END, DATA_START

ALL = "All"

# Preset -> (from, to). All computed from AS_OF_DATE, never datetime.now().
PRESETS: dict[str, tuple[date, date]] = {
    "this_month": (AS_OF_DATE.replace(day=1), AS_OF_DATE),
    "this_quarter": (
        AS_OF_DATE.replace(month=((AS_OF_DATE.month - 1) // 3) * 3 + 1, day=1),
        AS_OF_DATE,
    ),
    "ytd": (AS_OF_DATE.replace(month=1, day=1), AS_OF_DATE),
    "2025": (date(2025, 1, 1), date(2025, 12, 31)),
    "2026": (date(2026, 1, 1), date(2026, 12, 31)),
    "full_range": (DATA_START, DATA_END),
}

# Filter key -> dataframe column. Adding a dimension means one line here.
DIMENSIONS = {
    "region": "Region",
    "zone": "Zone",
    "cluster": "Cluster",
    "unit": "Unit_ID",
    "department": "Dept_Name",
    "stock_take_group": "Stock Take Group",
}


@dataclass
class Filters:
    region: str = ALL
    zone: str = ALL
    cluster: str = ALL
    unit: str = ALL
    department: str = ALL
    stock_take_group: str = ALL
    date_from: date = DATA_START
    date_to: date = DATA_END

    def as_dict(self) -> dict:
        """Echoed back in every response so the frontend can confirm state."""
        d = {k: getattr(self, k) for k in DIMENSIONS}
        d["date_from"] = self.date_from.isoformat()
        d["date_to"] = self.date_to.isoformat()
        return d

    def scope_label(self) -> str:
        """
        Human label for the current scope - drives the page subtitle so the
        user always knows what they are looking at. This is the affordance
        that replaces PRAVAH's N/R/Z/C/U tabs.
        """
        for key in ("unit", "cluster", "zone", "region"):
            v = getattr(self, key)
            if v != ALL:
                return v
        return "Network"


def get_filters(
    region: str = Query(ALL),
    zone: str = Query(ALL),
    cluster: str = Query(ALL),
    unit: str = Query(ALL),
    department: str = Query(ALL),
    stock_take_group: str = Query(ALL),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    preset: str | None = Query(None),
) -> Filters:
    """FastAPI dependency. Inject this into every dashboard endpoint."""
    if preset and preset in PRESETS:
        date_from, date_to = PRESETS[preset]
    return Filters(
        region=region, zone=zone, cluster=cluster, unit=unit,
        department=department, stock_take_group=stock_take_group,
        date_from=date_from or DATA_START,
        date_to=date_to or DATA_END,
    )


def apply(df: pd.DataFrame, f: Filters, date_col: str = "Date") -> pd.DataFrame:
    """
    Apply the filter set to any fact table.

    date_col differs per table (Purchase_Data uses PO_Date) - the only
    per-table variation allowed. A dimension is skipped where the table has no
    such column, or where the column is entirely null (purchase has no
    department), rather than returning an empty frame.
    """
    mask = (
        (df[date_col] >= pd.Timestamp(f.date_from))
        & (df[date_col] <= pd.Timestamp(f.date_to))
    )
    for key, col in DIMENSIONS.items():
        value = getattr(f, key)
        if value == ALL or col not in df.columns:
            continue
        if df[col].isna().all():
            continue
        mask &= df[col] == value
    return df.loc[mask]
