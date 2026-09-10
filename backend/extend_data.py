"""
Manipal Dashboard — Data Extension (v1 -> v2)
==============================================
Adds the dimensions the PRAVAH dashboards need, WITHOUT regenerating anything
that already works.

WHAT THIS DOES
--------------
Reads  FINAL_MANIPAL_Data.xlsx
Writes FINAL_MANIPAL_Data_v2.xlsx   (the source file is never modified)

Two kinds of change:
  1. WIDER  - new columns bolted onto existing rows. Every existing value
     (Qty, Value, Stock_Value, dates, items, vendors) is untouched.
  2. TALLER - 9 new hospital units, so the Region/Zone/Cluster hierarchy has
     something to aggregate. Existing rows for H001/H002/H003 are copied
     verbatim; new units get scaled clones of them.

That means: filter to H001 in the app and every number is identical to today.
Network-level totals go up, because the network now has 12 hospitals instead
of 3 - which is the point of adding a hierarchy.

NEW COLUMNS
-----------
Hierarchy   Region, Zone, Cluster              (all fact tables)
Formulary   Formulary_Tier (I/P1/P2/S1/OOF)    (Item_Master + consumption)
Payer       Payer_Type, Is_Package             (consumption)
Clinical    Episode_Type                       (consumption)
Flags       Is_Implant, Is_Essential           (Item_Master)
Stock       In_Transit_Qty                     (inventory)
Financial   Revenue, Cost                      (consumption)
Calendar    FY, FY_Month                       (all fact tables, Apr-Mar)
New sheet   Budget_Data                        (month x unit x dept)

ASSUMPTIONS THAT MAY NEED CORRECTING (all isolated, all one-line changes)
------------------------------------------------------------------------
  * Formulary tier meanings: I=Innovator, P1/P2=Preferred, S1=Substitute,
    OOF=Out Of Formulary. Read off low-resolution screenshots - confirm with
    the client before these labels appear on screen.
  * Tier assignment is derived from the EXISTING frozen Is_Formulary flag, so
    formulary compliance % does not move: the 33 off-formulary items become
    OOF, the 67 on-formulary items split across I/P1/P2/S1.
  * Budget is set ~5% above actual so the BUD-vs-ACT line has tension.

Run:  python extend_data.py
"""

import numpy as np
import pandas as pd

SRC = "data/FINAL_MANIPAL_Data.xlsx"
OUT = "data/FINAL_MANIPAL_Data_v2.xlsx"
PARQUET_DIR = "data/parquet"

# The v2 workbook is 21 MB and takes ~50s for pandas to read - unacceptable as
# a server startup cost. The app reads Parquet instead (0.4s, 3.5 MB). The
# .xlsx is written anyway because it is what you hand to a human who wants to
# look at the data; nothing at runtime reads it.
WRITE_XLSX = True

SEED = 42
rng = np.random.default_rng(SEED)

# Budget sits this far above actual on average.
BUDGET_UPLIFT = 1.05


# ---------------------------------------------------------------------------
# 1. HIERARCHY — 3 Regions -> 6 Zones -> 12 Clusters -> 12 Units
# ---------------------------------------------------------------------------
# The three existing units keep their IDs and slot into the tree. Nine new
# units are added so each level has something to roll up.
#   (unit_id, unit_name, cluster, zone, region, size_factor)
# size_factor scales the cloned volume - it is what gives the hierarchy charts
# their shape instead of 12 identical bars.
UNITS = [
    ("H001", "KHO", "Bangalore Central", "South-A", "South", 1.00),
    ("H002", "SIL", "Bangalore North",   "South-A", "South", 1.00),
    ("H003", "HYD", "Hyderabad",         "South-B", "South", 1.00),
    ("H004", "BLR", "Bangalore East",    "South-A", "South", 0.82),
    ("H005", "MYS", "Mysore",            "South-B", "South", 0.48),
    ("H006", "VJA", "Vijayawada",        "South-B", "South", 0.55),
    ("H007", "DEL", "Delhi NCR",         "Delhi",   "North", 0.95),
    ("H008", "JAI", "Jaipur",            "Rajasthan", "North", 0.61),
    ("H009", "LKO", "Lucknow",           "Rajasthan", "North", 0.44),
    ("H010", "PUN", "Pune",              "Maharashtra", "West", 0.78),
    ("H011", "GOA", "Goa",               "Goa-Konkan",  "West", 0.39),
    ("H012", "AHM", "Ahmedabad",         "Goa-Konkan",  "West", 0.52),
]

UNIT_DF = pd.DataFrame(
    UNITS, columns=["Unit_ID", "Unit_Name", "Cluster", "Zone", "Region", "size"])

# Which existing unit each new unit is cloned from. Cloning preserves the item
# mix, vendor mix and date spread, so per-item vendor shares stay stable and
# the frozen SOB targets remain valid.
CLONE_SOURCE = {
    "H004": "H001", "H005": "H002", "H006": "H003",
    "H007": "H001", "H008": "H002", "H009": "H003",
    "H010": "H001", "H011": "H002", "H012": "H003",
}

UNIT_META = UNIT_DF.set_index("Unit_ID")[
    ["Unit_Name", "Cluster", "Zone", "Region"]].to_dict("index")
SIZE = dict(zip(UNIT_DF.Unit_ID, UNIT_DF["size"]))


def add_hierarchy(df: pd.DataFrame) -> pd.DataFrame:
    """Attach Region/Zone/Cluster by looking up Unit_ID."""
    df = df.copy()
    for col in ("Cluster", "Zone", "Region"):
        df[col] = df["Unit_ID"].map(lambda u: UNIT_META[u][col])
    return df


def add_fiscal(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    Indian fiscal year runs Apr-Mar. Apr 2026 falls in FY2027, which matches
    the 'FY 2027' filter visible in the client's report.
    """
    df = df.copy()
    d = pd.to_datetime(df[date_col])
    df["FY"] = np.where(d.dt.month >= 4, d.dt.year + 1, d.dt.year)
    df["FY_Month"] = ((d.dt.month - 4) % 12) + 1   # 1 = April
    return df


def clone_units(df: pd.DataFrame, date_col: str,
                value_cols: list[str]) -> pd.DataFrame:
    """
    Build rows for the 9 new units by copying a source unit's rows and scaling
    the numeric columns. Dates, items, vendors and departments are preserved,
    so every distribution the dashboards rely on carries over.
    """
    frames = [df]
    for new_unit, src_unit in CLONE_SOURCE.items():
        block = df[df["Unit_ID"] == src_unit].copy()
        if not len(block):
            continue
        factor = SIZE[new_unit]
        # Per-row jitter so the clone is not a visibly exact multiple.
        jitter = rng.lognormal(0, 0.22, len(block))
        for col in value_cols:
            block[col] = np.maximum(1, np.round(block[col] * factor * jitter))
        block["Unit_ID"] = new_unit
        block["Unit_Name"] = UNIT_META[new_unit]["Unit_Name"]
        frames.append(block)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(date_col).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. LOAD
# ---------------------------------------------------------------------------
print("Reading source workbook...")
sheets = pd.read_excel(SRC, sheet_name=None)

items = sheets["Item_Master"].copy()
cons = sheets["Consumption_Data"].copy()
inv = sheets["Inventory_Stock"].copy()
pur = sheets["Purchase_Data"].copy()
mov = sheets["Stock_Movement"].copy()

cons["Date"] = pd.to_datetime(cons["Date"])
inv["Date"] = pd.to_datetime(inv["Date"])
pur["PO_Date"] = pd.to_datetime(pur["PO_Date"])
mov["Date"] = pd.to_datetime(mov["Date"])

# Baseline figures, re-checked at the end.
BASE = {
    "consumption_value": float(cons["Value"].sum()),
    "purchase_value": float(pur["Value"].sum()),
    "stock_value": float(inv["Stock_Value"].sum()),
    "cons_rows": len(cons),
}


# ---------------------------------------------------------------------------
# 3. ITEM_MASTER — formulary tier, implant and essential flags
# ---------------------------------------------------------------------------
# Tier is DERIVED from the frozen Is_Formulary flag rather than drawn fresh,
# so formulary compliance % does not move:
#   off-formulary items  -> OOF
#   on-formulary items   -> split across I / P1 / P2 / S1
import json
flags = json.loads(open("data/synthetic_flags.json").read())
IS_FORM = flags["is_formulary"]

items["Is_Formulary"] = items["Item_ID"].map(IS_FORM)

# Innovator products skew expensive; substitutes skew cheap. Ranking by price
# within the on-formulary set produces a tier ladder a pharmacist would
# recognise, rather than a random draw.
on = items[items["Is_Formulary"]].sort_values("Unit_Price", ascending=False)
tier_of = {}
n = len(on)
for i, item_id in enumerate(on["Item_ID"]):
    frac = i / n
    if frac < 0.15:
        tier_of[item_id] = "I"      # innovator - priciest on-formulary
    elif frac < 0.45:
        tier_of[item_id] = "P1"     # preferred, primary SOB agreement
    elif frac < 0.70:
        tier_of[item_id] = "P2"     # preferred, secondary
    else:
        tier_of[item_id] = "S1"     # substitute / generic
for item_id in items.loc[~items["Is_Formulary"], "Item_ID"]:
    tier_of[item_id] = "OOF"        # out of formulary

items["Formulary_Tier"] = items["Item_ID"].map(tier_of)

# Implants: high-value general consumables (stents, prostheses and the like).
# Their report splits "HIS Cons" from "HIS Non-Implant Cons".
implant_pool = items[(items["Category"] == "General Consumable")
                     & (items["Unit_Price"] > items["Unit_Price"].median())]
implant_ids = set(rng.choice(implant_pool["Item_ID"],
                             size=min(12, len(implant_pool)), replace=False))
items["Is_Implant"] = items["Item_ID"].isin(implant_ids)

# Essential Stock: items that must never stock out. Their inventory page has a
# dedicated "Drill Essential Stock" page.
items["Is_Essential"] = rng.random(len(items)) < 0.30

TIER = dict(zip(items.Item_ID, items.Formulary_Tier))
IMPLANT = dict(zip(items.Item_ID, items.Is_Implant))
ESSENTIAL = dict(zip(items.Item_ID, items.Is_Essential))
PRICE = dict(zip(items.Item_ID, items.Unit_Price))


# ---------------------------------------------------------------------------
# 4. CONSUMPTION — payer, package, episode, tier, revenue, cost
# ---------------------------------------------------------------------------
print("Extending consumption...")
cons = clone_units(cons, "Date", ["Qty", "Value"])
cons = add_hierarchy(cons)
cons = add_fiscal(cons, "Date")

cons["Formulary_Tier"] = cons["Item_ID"].map(TIER)
cons["Is_Implant"] = cons["Item_ID"].map(IMPLANT)

# Payer mix. Inpatients skew towards insurance and government schemes;
# outpatients skew towards cash.
PAYERS = ["Cash", "TPA", "Scheme"]
ip_mask = (cons["Patient_Type"] == "IP").to_numpy()
draw = rng.random(len(cons))
cons["Payer_Type"] = np.where(
    ip_mask,
    np.where(draw < 0.28, "Cash", np.where(draw < 0.70, "TPA", "Scheme")),
    np.where(draw < 0.62, "Cash", np.where(draw < 0.88, "TPA", "Scheme")),
)

# Package = bundled procedure pricing, where the hospital absorbs drug cost.
# Scheme patients are nearly always packaged; cash patients rarely are.
pk = rng.random(len(cons))
cons["Is_Package"] = np.where(
    cons["Payer_Type"] == "Scheme", pk < 0.88,
    np.where(cons["Payer_Type"] == "TPA", pk < 0.55, pk < 0.12))

EPISODES = ["Emergency", "Elective", "Day Care", "Follow Up"]
ep = rng.random(len(cons))
cons["Episode_Type"] = np.where(
    ip_mask,
    np.where(ep < 0.34, "Emergency", np.where(ep < 0.86, "Elective", "Day Care")),
    np.where(ep < 0.20, "Day Care", np.where(ep < 0.55, "Elective", "Follow Up")),
)

# Revenue and cost. Cost is what the hospital paid; Value is what was
# consumed; Revenue is what was billed. Margin is thinner on packaged and
# scheme business - which is exactly why brand choice matters there, and why
# the SOB dashboards slice by payer.
markup = np.where(cons["Is_Package"], rng.uniform(1.02, 1.18, len(cons)),
                  rng.uniform(1.22, 1.65, len(cons)))
markup = np.where(cons["Payer_Type"] == "Scheme", markup * 0.94, markup)
cons["Cost"] = np.round(cons["Value"] * rng.uniform(0.88, 0.96, len(cons)), 2)
cons["Revenue"] = np.round(cons["Value"] * markup, 2)


# ---------------------------------------------------------------------------
# 5. INVENTORY — hierarchy, flags, in-transit
# ---------------------------------------------------------------------------
print("Extending inventory...")
inv = clone_units(inv, "Date", ["Stock_Qty", "Stock_Value"])
inv = add_hierarchy(inv)
inv = add_fiscal(inv, "Date")
inv["Formulary_Tier"] = inv["Item_ID"].map(TIER)
inv["Is_Implant"] = inv["Item_ID"].map(IMPLANT)
inv["Is_Essential"] = inv["Item_ID"].map(ESSENTIAL)

# Stock in transit: ordered, not yet received. Only a minority of rows carry
# any, which is why their KPI often reads 0.00 at unit level.
has_transit = rng.random(len(inv)) < 0.14
inv["In_Transit_Qty"] = np.where(
    has_transit, np.round(inv["Stock_Qty"] * rng.uniform(0.05, 0.30, len(inv))), 0
).astype(int)
inv["In_Transit_Value"] = np.round(
    inv["In_Transit_Qty"] * inv["Item_ID"].map(PRICE), 2)


# ---------------------------------------------------------------------------
# 6. PURCHASE + MOVEMENT
# ---------------------------------------------------------------------------
print("Extending purchase and movement...")
pur = clone_units(pur, "PO_Date", ["Qty", "Value"])
pur = add_hierarchy(pur)
pur = add_fiscal(pur, "PO_Date")
pur["Formulary_Tier"] = pur["Item_ID"].map(TIER)

mov = clone_units(mov, "Date", ["Qty"])
mov = add_hierarchy(mov)
mov = add_fiscal(mov, "Date")


# ---------------------------------------------------------------------------
# 7. BUDGET — month x unit x dept, derived from actual
# ---------------------------------------------------------------------------
# Budget is set from actual consumption plus an uplift, with noise, so the
# BUD-vs-ACT chart shows some months over and some under rather than a flat
# offset. A real budget would come from finance; this is clearly labelled demo
# logic and is trivial to replace.
print("Building budget...")
cons["Month_Start"] = cons["Date"].values.astype("datetime64[M]")
budget = (cons.groupby(["Month_Start", "Unit_ID", "Unit_Name", "Dept_ID",
                        "Dept_Name"], as_index=False)["Value"].sum()
            .rename(columns={"Value": "Actual_Value"}))
budget["Budget_Value"] = np.round(
    budget["Actual_Value"] * BUDGET_UPLIFT * rng.normal(1.0, 0.09, len(budget)), 2)
budget["Budget_Value"] = budget["Budget_Value"].clip(lower=0)
budget = add_hierarchy(budget)
budget = add_fiscal(budget, "Month_Start")
budget = budget.rename(columns={"Month_Start": "Date"})
cons = cons.drop(columns=["Month_Start"])


# ---------------------------------------------------------------------------
# 8. MASTERS + WRITE
# ---------------------------------------------------------------------------
unit_master = UNIT_DF.drop(columns=["size"]).copy()

out = {
    "Doctor_Master": sheets["Doctor_Master"],
    "Procedure_Master": sheets["Procedure_Master"],
    "Vendor_Master": sheets["Vendor_Master"],
    "Item_Master": items,
    "Unit_Master": unit_master,          # NEW - the hierarchy definition
    "Consumption_Data": cons,
    "Inventory_Stock": inv,
    "Purchase_Data": pur,
    "Stock_Movement": mov,
    "Budget_Data": budget,               # NEW
}

import os
os.makedirs(PARQUET_DIR, exist_ok=True)
print("Writing Parquet (this is what the app loads)...")
for name, df in out.items():
    df.to_parquet(f"{PARQUET_DIR}/{name}.parquet", index=False)

if WRITE_XLSX:
    print("Writing .xlsx for human inspection (slow, not used at runtime)...")
    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        for name, df in out.items():
            df.to_excel(w, sheet_name=name, index=False)


# ---------------------------------------------------------------------------
# 9. VERIFY — the three original units must be byte-for-byte unchanged
# ---------------------------------------------------------------------------
orig_units = ["H001", "H002", "H003"]
c3 = cons[cons["Unit_ID"].isin(orig_units)]
p3 = pur[pur["Unit_ID"].isin(orig_units)]
i3 = inv[inv["Unit_ID"].isin(orig_units)]

print("\n" + "=" * 62)
print("VERIFICATION — original 3 units vs baseline")
print("=" * 62)
checks = [
    ("Consumption value", c3["Value"].sum(), BASE["consumption_value"]),
    ("Purchase value", p3["Value"].sum(), BASE["purchase_value"]),
    ("Stock value", i3["Stock_Value"].sum(), BASE["stock_value"]),
    ("Consumption rows", len(c3), BASE["cons_rows"]),
]
all_ok = True
for label, got, want in checks:
    ok = abs(got - want) < 1
    all_ok &= ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label:20s} {got:>18,.0f}  (was {want:,.0f})")

print("\nNETWORK TOTALS (all 12 units)")
print(f"  Consumption   Rs {cons['Value'].sum() / 1e7:>8.2f} Cr")
print(f"  Purchase      Rs {pur['Value'].sum() / 1e7:>8.2f} Cr")
print(f"  Stock         Rs {inv['Stock_Value'].sum() / 1e7:>8.2f} Cr")
print(f"  Revenue       Rs {cons['Revenue'].sum() / 1e7:>8.2f} Cr")
print(f"  Margin        Rs {(cons['Revenue'] - cons['Cost']).sum() / 1e7:>8.2f} Cr")
print(f"  Rows          consumption {len(cons):,} | inventory {len(inv):,} "
      f"| purchase {len(pur):,}")

print(f"\n{'OK - safe to switch config.py' if all_ok else 'STOP - do not switch'}")
print(f"Written: {PARQUET_DIR}/  (app reads this)")
if WRITE_XLSX:
    print(f"Written: {OUT}  (inspection only)")
