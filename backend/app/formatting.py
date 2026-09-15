"""Indian number formatting. The client reads in lakh/crore, not millions."""


def inr_compact(value: float) -> str:
    """
    Always expressed in Crores - matches the client's own convention, "All
    Values are in Crores", visible in the header of every PRAVAH screenshot.
    Used on KPI cards and chart axes. Table cells keep exact Rupees via
    inr_full - a per-item row showing "Rs 0.00 Cr" would be useless.
    """
    v = float(value or 0)
    sign = "-" if v < 0 else ""
    cr = abs(v) / 1e7
    return f"{sign}₹{cr:.2f} Cr"


def inr_full(value: float) -> str:
    """1234567 -> '₹12,34,567' with Indian digit grouping (2,2,3)."""
    v = int(round(float(value or 0)))
    sign = "-" if v < 0 else ""
    s = str(abs(v))
    if len(s) <= 3:
        return f"{sign}₹{s}"
    last3, rest = s[-3:], s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return f"{sign}₹{','.join(parts)},{last3}"


def qty_compact(value: float) -> str:
    """Large unit counts, same grouping without the currency symbol."""
    return inr_full(value).replace("₹", "")


def pct(value: float, digits: int = 1) -> str:
    return f"{float(value or 0):.{digits}f}%"
