"""
Manipal Dashboard — Value Scale-Up (x10)
=========================================
Run AFTER extend_data.py and fix_sob_mix.py. Rewrites the monetary columns in
data/parquet/*.parquet, multiplying every value by SCALE.

WHY
---
Feedback: the demo network total (Rs 54 Cr consumption, Rs 60 Cr stock) reads
too small next to PRAVAH's real figures (Rs 877 Cr HIS consumption, Rs 187 Cr
inventory value). This scales the synthetic network up so the absolute
numbers sit in a believable enterprise range.

HOW
---
Only MONETARY columns are multiplied. Quantities, item/doctor/vendor counts,
dates, percentages, and the frozen formulary/SOB flags in
synthetic_flags.json are all left untouched.

Every pair of values that feeds a ratio is scaled by the exact same factor,
so every %-based KPI already built - formulary compliance, SOB compliance,
budget utilisation, Inventory Days - reads IDENTICALLY before and after this
script runs. Only the absolute Rupee figures change. Verified below.

SAFETY: a marker file prevents running this twice (which would 100x instead
of 10x). Delete data/parquet/.scaled_x10 if you deliberately want to re-run.

Run:  python scale_values.py
"""

import os

import pandas as pd

PARQUET = "data/parquet"
SCALE = 10
MARKER = f"{PARQUET}/.scaled_x{SCALE}"

if os.path.exists(MARKER):
    raise SystemExit(
        f"Already scaled by {SCALE}x (marker file found at {MARKER}).\n"
        f"Running again would multiply by {SCALE * SCALE}x, not {SCALE}x.\n"
        f"Delete the marker file first if that is really what you want."
    )

TARGETS = {
    "Consumption_Data.parquet": ["Value", "Revenue", "Cost"],
    "Inventory_Stock.parquet": ["Stock_Value", "In_Transit_Value"],
    "Purchase_Data.parquet": ["Value"],
    "Budget_Data.parquet": ["Actual_Value", "Budget_Value"],
    "Item_Master.parquet": ["Unit_Price"],
}

before_totals = {}
for fname, cols in TARGETS.items():
    path = f"{PARQUET}/{fname}"
    df = pd.read_parquet(path)
    present = [c for c in cols if c in df.columns]
    before_totals[fname] = {c: float(df[c].sum()) for c in present}
    for c in present:
        df[c] = df[c] * SCALE
    df.to_parquet(path, index=False)
    print(f"{fname}: scaled {present}")

open(MARKER, "w").write("scaled\n")

print("\n" + "=" * 60)
print("VERIFY: each column scaled by exactly %sx" % SCALE)
all_ok = True
for fname, cols in before_totals.items():
    df = pd.read_parquet(f"{PARQUET}/{fname}")
    for c, b in cols.items():
        a = float(df[c].sum())
        ratio = (a / b) if b else 0
        ok = abs(ratio - SCALE) < 0.01
        all_ok &= ok
        print(f"  {'PASS' if ok else 'FAIL'}  {fname}:{c:14s} "
              f"{b/1e7:>8.2f} -> {a/1e7:>9.2f} Cr  (x{ratio:.2f})")

print(f"\n{'OK - safe to restart the backend' if all_ok else 'STOP - a column did not scale correctly'}")
