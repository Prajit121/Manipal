"""
Manipal Dashboard — Store Location (fake dimension)
====================================================
Run AFTER extend_data.py / fix_sob_mix.py / scale_values.py. Adds a
"Store_Location" column to Consumption_Data.parquet and Inventory_Stock.parquet.

WHY
---
PRAVAH's Consumption and Inventory pages break down by physical in-hospital
location - "IP PHARMACY MKI", "OT STORE MHD", "CATH LAB PHARMACY" - not by
clinical department. We have no such dimension in the source data; this
generates one in the same style (location type + hospital unit code) so the
Top-10-by-location charts have something real to show.

THIS IS FLAGGED AS FAKE, ON PURPOSE - invented at the client's request, not
read off any document. Every KPI, every other chart, and the underlying
Value/Stock_Value figures are untouched; this only adds one new column.

Fixed seed (42) makes this deterministic - re-running reproduces the exact
same assignment.

Run:  python add_store_location.py
"""

import numpy as np
import pandas as pd

PARQUET = "data/parquet"
SEED = 42
rng = np.random.default_rng(SEED)

LOCATIONS = [
    "IP Pharmacy", "OT Store", "OT Pharmacy", "1st Floor OT",
    "Cath Lab Pharmacy", "Cath Lab Store", "Ward Pharmacy",
    "Emergency Pharmacy", "General Store", "Bulk Pharmacy",
]

WEIGHTS_CONS = {
    "IP Pharmacy": 3.0, "OT Store": 2.2, "OT Pharmacy": 1.8,
    "1st Floor OT": 1.6, "Cath Lab Pharmacy": 1.4, "Cath Lab Store": 1.2,
    "Ward Pharmacy": 1.1, "Emergency Pharmacy": 1.0,
    "General Store": 0.7, "Bulk Pharmacy": 0.6,
}
WEIGHTS_INV = {
    "Bulk Pharmacy": 3.2, "General Store": 2.6, "Ward Pharmacy": 1.8,
    "OT Pharmacy": 1.6, "IP Pharmacy": 1.4, "Cath Lab Store": 1.3,
    "Emergency Pharmacy": 1.1, "OT Store": 1.0,
    "1st Floor OT": 0.8, "Cath Lab Pharmacy": 0.7,
}


def assign(df: pd.DataFrame, weights: dict) -> pd.Series:
    probs = np.array([weights[loc] for loc in LOCATIONS])
    probs = probs / probs.sum()
    draws = rng.choice(LOCATIONS, size=len(df), p=probs)
    return pd.Series(draws, index=df.index) + " - " + df["Unit_Name"].astype(str)


cons = pd.read_parquet(f"{PARQUET}/Consumption_Data.parquet")
inv = pd.read_parquet(f"{PARQUET}/Inventory_Stock.parquet")

cons["Store_Location"] = assign(cons, WEIGHTS_CONS)
inv["Store_Location"] = assign(inv, WEIGHTS_INV)

cons.to_parquet(f"{PARQUET}/Consumption_Data.parquet", index=False)
inv.to_parquet(f"{PARQUET}/Inventory_Stock.parquet", index=False)

print("Store_Location added.\n")
print("Top 10 by Consumption value:")
print((cons.groupby("Store_Location")["Value"].sum()
       .sort_values(ascending=False).head(10) / 1e7).round(2).to_string())
print("\nTop 10 by Inventory value (latest snapshot):")
snap = inv[inv["Date"] == inv["Date"].max()]
print((snap.groupby("Store_Location")["Stock_Value"].sum()
       .sort_values(ascending=False).head(10) / 1e7).round(2).to_string())
