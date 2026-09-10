"""
Loads the Parquet dataset ONCE at startup and caches the joined frames.

Every fact table is pre-joined to its masters here, so routers never do joins.
A join done differently in two routers is how the same KPI ends up with two
different values on two pages.
"""

import json
from functools import lru_cache

import pandas as pd

from app.config import FLAGS_PATH, PARQUET_DIR


def _read(name: str) -> pd.DataFrame:
    return pd.read_parquet(PARQUET_DIR / f"{name}.parquet")


class DataStore:
    """Holds every prepared DataFrame. Built once, read many."""

    def __init__(self) -> None:
        # Frozen synthetic fields - loaded from a committed JSON file, never
        # regenerated at runtime. Regenerating would let numbers drift between
        # the deck screenshots and the live demo.
        flags = json.loads(FLAGS_PATH.read_text())
        self.is_formulary = flags["is_formulary"]
        self.sob_targets = flags["sob_targets"]

        # --- Masters ---
        self.items = _read("Item_Master")
        self.doctors = _read("Doctor_Master")
        self.vendors = _read("Vendor_Master")
        self.units = _read("Unit_Master")

        # --- Consumption ---
        c = _read("Consumption_Data")
        c["Date"] = pd.to_datetime(c["Date"])
        c = c.merge(
            self.items[["Item_ID", "Molecule", "Category", "Unit_Price",
                        "Is_Formulary", "Is_Essential"]],
            on="Item_ID", how="left",
        ).merge(
            self.doctors[["Doctor_ID", "Specialty"]], on="Doctor_ID", how="left",
        )
        c["Month_Start"] = c["Date"].values.astype("datetime64[M]")
        self.consumption = c

        # --- Inventory ---
        i = _read("Inventory_Stock")
        for col in ("Date", "Expiry_Date", "GRN Date"):
            i[col] = pd.to_datetime(i[col])
        i = i.merge(
            self.items[["Item_ID", "Molecule", "Category"]],
            on="Item_ID", how="left",
        )
        i["Month_Start"] = i["Date"].values.astype("datetime64[M]")
        self.inventory = i

        # --- Purchase ---
        p = _read("Purchase_Data")
        p["PO_Date"] = pd.to_datetime(p["PO_Date"])
        p = p.merge(
            self.items[["Item_ID", "Molecule", "Category"]],
            on="Item_ID", how="left",
        )
        p["Month_Start"] = p["PO_Date"].values.astype("datetime64[M]")
        # Purchase has no Dept dimension. Explicit null column so the shared
        # department filter applies uniformly without special-casing.
        p["Dept_Name"] = None
        self.purchase = p

        # --- Stock movement ---
        m = _read("Stock_Movement")
        m["Date"] = pd.to_datetime(m["Date"])
        m["Month_Start"] = m["Date"].values.astype("datetime64[M]")
        m["Dept_Name"] = None
        self.movement = m

        # --- Budget (month x unit x dept) ---
        b = _read("Budget_Data")
        b["Date"] = pd.to_datetime(b["Date"])
        b["Month_Start"] = b["Date"].values.astype("datetime64[M]")
        self.budget = b

        # --- Filter dropdown lookups ---
        self.departments = sorted(c["Dept_Name"].dropna().unique().tolist())
        self.regions = sorted(self.units["Region"].unique().tolist())
        self.zones = sorted(self.units["Zone"].unique().tolist())
        self.clusters = sorted(self.units["Cluster"].unique().tolist())
        self.unit_options = self.units[
            ["Unit_ID", "Unit_Name", "Cluster", "Zone", "Region"]
        ].to_dict("records")


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    """FastAPI dependency. lru_cache makes this a singleton."""
    return DataStore()
