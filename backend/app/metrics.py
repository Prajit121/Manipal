"""
THE metrics layer. Every number that appears on more than one page is computed
here and ONLY here.

The most important file in the backend: "Total Consumption Value" appears on
the Consumption page and again on the Formulary page. If two routers each
compute it themselves they will drift - a different null handling, a join that
fans out rows. The client opens two tabs, compares, and sees Rs 4.2 Cr against
Rs 4.4 Cr. At that point the demo is over.

Rule: routers call these functions. Routers never write their own .sum().
"""

import pandas as pd

from app.config import FORMULARY_TARGET_PCT, SOB_OPPORTUNITY_PCT


def total_value(df: pd.DataFrame, col: str = "Value") -> float:
    return float(df[col].sum()) if len(df) else 0.0


def total_qty(df: pd.DataFrame, col: str = "Qty") -> float:
    return float(df[col].sum()) if len(df) else 0.0


def safe_pct(numerator: float, denominator: float) -> float:
    """Percentage that returns 0.0 instead of exploding on an empty filter."""
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def consumption_kpis(df: pd.DataFrame) -> dict:
    val = total_value(df)
    ip = total_value(df[df["Patient_Type"] == "IP"])
    return {
        "total_value": val,
        "total_qty": total_qty(df),
        "ip_pct": safe_pct(ip, val),
        "op_pct": safe_pct(val - ip, val),
        "avg_per_txn": round(val / len(df), 2) if len(df) else 0.0,
        "txn_count": len(df),
    }


def monthly_trend(df: pd.DataFrame, value_col: str = "Value") -> pd.DataFrame:
    """Month-by-month totals. Used by every trend chart on every page."""
    if not len(df):
        return pd.DataFrame(columns=["Month_Start", value_col])
    return (
        df.groupby("Month_Start", as_index=False)[value_col]
        .sum()
        .sort_values("Month_Start")
    )


def year_over_year(df: pd.DataFrame, value_col: str = "Value") -> dict:
    """Two series keyed by month number, one per year, for the 2025-vs-2026
    overlaid line chart the spec asks for on multiple pages."""
    if not len(df):
        return {}
    t = df.copy()
    t["_y"] = t["Month_Start"].dt.year
    t["_m"] = t["Month_Start"].dt.month
    g = t.groupby(["_y", "_m"], as_index=False)[value_col].sum()
    return {
        int(y): grp.sort_values("_m")[["_m", value_col]]
        .rename(columns={"_m": "month", value_col: "value"})
        .to_dict("records")
        for y, grp in g.groupby("_y")
    }


def breakdown(df: pd.DataFrame, by: str, value_col: str = "Value",
              top_n: int | None = None) -> pd.DataFrame:
    """Generic 'value by dimension' aggregation, sorted descending."""
    if not len(df):
        return pd.DataFrame(columns=[by, value_col])
    g = (df.groupby(by, as_index=False)[value_col].sum()
           .sort_values(value_col, ascending=False))
    return g.head(top_n) if top_n else g


def formulary_kpis(df: pd.DataFrame) -> dict:
    val = total_value(df)
    on = total_value(df[df["Is_Formulary"] == True])
    off_items = df.loc[df["Is_Formulary"] == False, "Item_ID"].nunique()
    return {
        "compliance_pct": safe_pct(on, val),
        "on_formulary_value": on,
        "off_formulary_value": val - on,
        "off_formulary_items": int(off_items),
        "target_pct": FORMULARY_TARGET_PCT,
    }


def vendor_share_by_item(df: pd.DataFrame) -> pd.DataFrame:
    """Per item: each vendor's share of that item's purchase value.
    Feeds both SOB dashboards, so it lives here not in either router."""
    if not len(df):
        return pd.DataFrame(columns=["Item_ID", "Vendor_ID", "Value", "share_pct"])
    g = df.groupby(["Item_ID", "Vendor_ID"], as_index=False)["Value"].sum()
    totals = g.groupby("Item_ID")["Value"].transform("sum")
    g["share_pct"] = (g["Value"] / totals * 100).round(2)
    return g


def top_vendor_per_item(df: pd.DataFrame) -> pd.DataFrame:
    """The dominant vendor for each item, with its share."""
    g = vendor_share_by_item(df)
    if not len(g):
        return g
    return g.sort_values("share_pct", ascending=False).groupby("Item_ID").head(1)


def sob_opportunities(df: pd.DataFrame) -> pd.DataFrame:
    """Items where no single vendor holds SOB_OPPORTUNITY_PCT share.
    DEMO HEURISTIC - clearly labelled, easy to replace with a real rule."""
    top = top_vendor_per_item(df)
    if not len(top):
        return top
    top = top.copy()
    top["is_opportunity"] = top["share_pct"] < SOB_OPPORTUNITY_PCT
    return top


def sob_compliance(df: pd.DataFrame, targets: dict) -> pd.DataFrame:
    """Actual vs agreed vendor share, per item. targets is the FROZEN
    synthetic commitment. Actual is recomputed on filtered data; target never
    changes."""
    shares = vendor_share_by_item(df)
    if not len(shares):
        return pd.DataFrame(
            columns=["Item_ID", "Vendor_ID", "target_pct", "actual_pct",
                     "variance_pct", "Value", "on_target"])
    rows = []
    for item_id, t in targets.items():
        vendor_id = t["vendor_id"]
        m = shares[(shares["Item_ID"] == item_id) & (shares["Vendor_ID"] == vendor_id)]
        if not len(m):
            continue
        actual = float(m["share_pct"].iloc[0])
        target = float(t["target_sob_pct"])
        rows.append({
            "Item_ID": item_id,
            "Vendor_ID": vendor_id,
            "target_pct": target,
            "actual_pct": actual,
            "variance_pct": round(actual - target, 2),
            "Value": float(m["Value"].iloc[0]),
            "on_target": actual >= target,
        })
    return pd.DataFrame(rows)


def inventory_kpis(df: pd.DataFrame) -> dict:
    val = total_value(df, "Stock_Value")
    nm = total_value(df[df["Moving/Non Moving"] == "Non Moving"], "Stock_Value")
    return {
        "total_stock_value": val,
        "total_stock_qty": total_qty(df, "Stock_Qty"),
        "non_moving_pct": safe_pct(nm, val),
        "near_expiry_items": int((df["Expiry/Near Expiry"] == "Near Expiry").sum()),
        "expired_items": int((df["Expiry/Near Expiry"] == "Expired").sum()),
        "expired_value": total_value(
            df[df["Expiry/Near Expiry"] == "Expired"], "Stock_Value"),
    }
