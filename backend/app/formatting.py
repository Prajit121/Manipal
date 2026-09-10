"""Indian number formatting. The client reads in lakh/crore, not millions."""


def inr_compact(value: float) -> str:
    """18000000 -> '₹1.80 Cr'. Used on KPI cards where space is tight."""
    v = float(value or 0)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e7:
        return f"{sign}₹{v / 1e7:.2f} Cr"
    if v >= 1e5:
        return f"{sign}₹{v / 1e5:.2f} L"
    if v >= 1e3:
        return f"{sign}₹{v / 1e3:.1f} K"
    return f"{sign}₹{v:.0f}"


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
