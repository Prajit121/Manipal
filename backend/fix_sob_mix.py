"""
Manipal Dashboard — SOB Mix Correction
======================================
Run AFTER extend_data.py. Reads and rewrites data/parquet/Consumption_Data.parquet.

WHY
---
extend_data.py assigned Payer_Type and Formulary_Tier independently, so the
tier mix came out nearly identical across payers (Cash 28.5% P1, Scheme 27.2%,
TPA 27.6%) and doctor adherence spanned only 34-51%. Both are the "uniform
random" failure: the SOB Compliance charts would show two near-identical
stacked bars, and a Top-10-Doctors chart would be ten bars the same height.

Neither is how this works in reality:
  * On scheme and packaged cases the HOSPITAL absorbs the drug cost, so there
    is direct margin pressure to prescribe the preferred brand.
  * On cash cases the patient pays, so innovator and off-formulary brands get
    used more freely.
  * Individual prescribers vary enormously. That variation is the entire point
    of a doctor-wise opportunity chart - it names who to talk to.

HOW
---
Tier is a property of the ITEM (brand X is the preferred brand for molecule Y).
A payer does not change an item's tier - it changes WHICH ITEM gets prescribed.
So this script reassigns Item_ID within the same molecule, never the tier
itself.

Value is PRESERVED EXACTLY on every row: when an item is switched, Qty is
recomputed as Value / new unit price. That means every figure already on the
dashboards - total consumption, budget utilisation, department mix, monthly
trend - is untouched. Only Item_ID, Item_Name and Qty move.

Run:  python fix_sob_mix.py
"""

import numpy as np
import pandas as pd

PARQUET = "data/parquet"
SEED = 42
rng = np.random.default_rng(SEED)

PREFERRED = {"I", "P1"}

# Probability that a non-preferred prescription gets switched to the preferred
# brand, by who is paying. Scheme highest (hospital absorbs cost), cash lowest.
SWITCH_BASE = {"Scheme": 0.78, "TPA": 0.58, "Cash": 0.34}
# Packaged cases are bundled-price, so the hospital eats the difference there
# too - extra pressure on top of the payer effect.
PACKAGE_BONUS = 0.12


def main() -> None:
    items = pd.read_parquet(f"{PARQUET}/Item_Master.parquet")
    cons = pd.read_parquet(f"{PARQUET}/Consumption_Data.parquet")

    before_total = float(cons["Value"].sum())
    before_pref = float(cons.loc[cons["Formulary_Tier"].isin(PREFERRED), "Value"].sum())

    price = dict(zip(items["Item_ID"], items["Unit_Price"]))
    name = dict(zip(items["Item_ID"], items["Item_Name"]))
    tier = dict(zip(items["Item_ID"], items["Formulary_Tier"]))
    molecule = dict(zip(items["Item_ID"], items["Molecule"]))

    # Preferred alternatives available for each molecule.
    pref_by_mol: dict[str, list[str]] = {}
    for item_id, mol in molecule.items():
        if tier[item_id] in PREFERRED:
            pref_by_mol.setdefault(mol, []).append(item_id)

    # Per-doctor adherence multiplier. Some prescribers are far better than
    # others; that spread is what makes the opportunity list actionable.
    doctors = sorted(cons["Doctor"].dropna().unique())
    doc_factor = dict(zip(doctors, rng.uniform(0.45, 1.35, len(doctors))))

    cons = cons.copy()
    cons["_mol"] = cons["Item_ID"].map(molecule)
    cons["_switchable"] = (
        ~cons["Formulary_Tier"].isin(PREFERRED)
        & cons["_mol"].isin(pref_by_mol)
    )

    base = cons["Payer_Type"].map(SWITCH_BASE).fillna(0.4).to_numpy()
    bonus = np.where(cons["Is_Package"].to_numpy(), PACKAGE_BONUS, 0.0)
    factor = cons["Doctor"].map(doc_factor).fillna(1.0).to_numpy()
    prob = np.clip((base + bonus) * factor, 0, 0.95)

    draw = rng.random(len(cons))
    do_switch = cons["_switchable"].to_numpy() & (draw < prob)

    print(f"Switching {do_switch.sum():,} of {len(cons):,} rows "
          f"({do_switch.mean() * 100:.1f}%)")

    new_item = cons["Item_ID"].to_numpy().copy()
    idx = np.flatnonzero(do_switch)
    for i in idx:
        options = pref_by_mol[cons["_mol"].iat[i]]
        new_item[i] = options[rng.integers(len(options))]

    cons["Item_ID"] = new_item
    cons["Item_Name"] = cons["Item_ID"].map(name)
    cons["Formulary_Tier"] = cons["Item_ID"].map(tier)

    # VALUE IS PRESERVED. Qty absorbs the price difference, so every total
    # already shown on the dashboards stays exactly the same.
    cons["Qty"] = np.maximum(
        1, np.round(cons["Value"] / cons["Item_ID"].map(price))).astype(int)

    cons = cons.drop(columns=["_mol", "_switchable"])
    cons.to_parquet(f"{PARQUET}/Consumption_Data.parquet", index=False)

    # --- Report -----------------------------------------------------------
    after_total = float(cons["Value"].sum())
    after_pref = float(cons.loc[cons["Formulary_Tier"].isin(PREFERRED), "Value"].sum())

    print("\n" + "=" * 58)
    print(f"  Total value  {'PRESERVED' if abs(after_total - before_total) < 1 else 'CHANGED - BUG'}"
          f"   {after_total / 1e7:.2f} Cr (was {before_total / 1e7:.2f} Cr)")
    print(f"  Preferred share  {before_pref / before_total * 100:.1f}%"
          f"  ->  {after_pref / after_total * 100:.1f}%")

    print("\n  Tier mix by payer (%):")
    p = cons.pivot_table(index="Payer_Type", columns="Formulary_Tier",
                         values="Value", aggfunc="sum")
    print(p.div(p.sum(axis=1), axis=0).mul(100).round(1).to_string()
          .replace("\n", "\n  "))

    adherence = cons.groupby("Doctor").apply(
        lambda g: g.loc[g["Formulary_Tier"].isin(PREFERRED), "Value"].sum()
        / g["Value"].sum() * 100,
        include_groups=False).sort_values()
    print(f"\n  Doctor adherence spread: {adherence.min():.0f}% to "
          f"{adherence.max():.0f}%")
    print(f"    worst: {adherence.index[0]} ({adherence.iloc[0]:.0f}%)")
    print(f"    best:  {adherence.index[-1]} ({adherence.iloc[-1]:.0f}%)")


if __name__ == "__main__":
    main()
