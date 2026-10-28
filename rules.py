"""Design defense layer: the purchase decision is made by code, not by the model.

The model only extracts facts. These four handbook checks (section 4) are applied
in Python using tables read straight from data/shop_handbook.md, so no text inside
a vendor document can argue its way to "recommend".
"""

import re
from functools import lru_cache
from pathlib import Path

HANDBOOK = Path(__file__).parent / "data" / "shop_handbook.md"
MAX_LEAD_DAYS = 21
MAX_MIN_ORDER = 600


def _section(text: str, number: int) -> str:
    m = re.search(rf"^## {number}\..*?(?=^## \d+\.|\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def _rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"^\|\s*-", line):
            rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows[1:]  # drop header


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


@lru_cache
def handbook_tables() -> dict:
    text = HANDBOOK.read_text(encoding="utf-8")
    approved = {_norm(r[1]): r[1] for r in _rows(_section(text, 5))}
    blocked = {_norm(r[0]): (r[0], r[1]) for r in _rows(_section(text, 6))}
    rows = _rows(_section(text, 9))
    catalogue = {r[0]: float(r[4].lstrip("$")) for r in rows}
    items = {r[0]: r[1] for r in rows}
    return {"approved": approved, "blocked": blocked, "catalogue": catalogue, "items": items}


def _words(text: str) -> set[str]:
    words = re.sub(r"['’]", "", (text or "").lower())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", words)}


def item_mismatch(sku: str | None, item: str | None) -> str | None:
    """Design check: the SKU must be for the item the document describes. A swapped SKU
    silently changes which max unit cost applies. Returns a problem or None."""
    name = handbook_tables()["items"].get(sku or "")
    if not name or not item:
        return None
    want = _words(name)
    if len(want & _words(item)) / len(want) >= 0.5:
        return None
    return f"SKU {sku} is '{name}' in the catalogue, but the document describes '{item}'"


def decide(vendor: str, sku: str | None, unit_price: float | None,
           lead_time_days: int | None, min_order: int | None) -> tuple[str, str]:
    """Apply the four purchasing checks. Returns (decision, one-sentence reason)."""
    t = handbook_tables()
    v = _norm(vendor)
    if v in t["blocked"]:
        name, status = t["blocked"][v]
        return "do_not_recommend", f"Approved vendor check fails: {name} is on the removed/pending list ({status.split('.')[0]})."
    if v not in t["approved"]:
        return "do_not_recommend", f"Approved vendor check fails: {vendor or 'the vendor'} is not on the approved vendor list."
    if not sku or sku not in t["catalogue"]:
        return "do_not_recommend", f"Price check cannot pass: SKU {sku or 'unknown'} is not in the catalogue."
    max_cost = t["catalogue"][sku]
    if unit_price is None:
        return "do_not_recommend", "Price check cannot pass: the document does not state a unit price."
    if unit_price > max_cost:
        return "do_not_recommend", f"Price check fails: ${unit_price:.2f} is above the ${max_cost:.2f} max unit cost for {sku}."
    if lead_time_days is None:
        return "do_not_recommend", "Lead time check cannot pass: the document does not state a lead time."
    if lead_time_days > MAX_LEAD_DAYS:
        return "do_not_recommend", f"Lead time check fails: {lead_time_days} days is more than the {MAX_LEAD_DAYS}-day limit."
    if min_order is None:
        return "do_not_recommend", "Minimum order check cannot pass: the document does not state a minimum order."
    if min_order > MAX_MIN_ORDER:
        return "do_not_recommend", f"Minimum order check fails: {min_order} units is more than the {MAX_MIN_ORDER}-unit limit."
    return "recommend", (
        f"All four checks pass: {t['approved'][v]} is approved, ${unit_price:.2f} is at or below the "
        f"${max_cost:.2f} max for {sku}, {lead_time_days} days is within {MAX_LEAD_DAYS}, "
        f"and {min_order} units is within {MAX_MIN_ORDER}."
    )
