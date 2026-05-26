import re
from typing import Optional, Tuple


GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


def validate_gstin(gstin: str) -> bool:
    if not gstin or len(gstin) != 15:
        return False
    return bool(GSTIN_PATTERN.match(gstin))


def format_gstin(gstin: str) -> Optional[str]:
    cleaned = gstin.strip().upper()
    if validate_gstin(cleaned):
        return cleaned
    return None


HSN_LENGTHS = {4: "4-digit HSN", 6: "6-digit HSN", 8: "8-digit HSN"}


def lookup_hsn(hsn: str) -> Optional[str]:
    hsn = hsn.strip()
    length = len(hsn)
    if length in HSN_LENGTHS:
        return HSN_LENGTHS[length]
    return None


SAC_SERVICES = {
    "998311": "Advertising services",
    "998312": "Market research services",
    "998313": "Public relations services",
    "998314": "Sales and marketing services",
    "998315": "Direct mail and fulfillment services",
    "998321": "Computer programming services",
    "998322": "Computer consultancy services",
    "998323": "Computer facilities management services",
    "998324": "Web hosting and cloud services",
    "998411": "Legal services",
    "998412": "Accounting and bookkeeping services",
    "998413": "Tax consultancy services",
    "998414": "Management consulting services",
    "998415": "Business consulting services",
    "998416": "Human resource consulting services",
    "998421": "Architectural services",
    "998422": "Engineering services",
    "998423": "Scientific and technical consulting",
    "998431": "Telecommunications services",
    "998432": "Internet services",
    "998511": "Educational services",
    "998512": "Health services",
    "998513": "Social welfare services",
    "998611": "Hotel and lodging services",
    "998612": "Food and beverage services",
    "998613": "Event management services",
    "998621": "Travel agency services",
    "998622": "Tour operator services",
    "998711": "Real estate services",
    "998712": "Rental and leasing services",
    "998811": "Transport of goods by road",
    "998812": "Transport of goods by rail",
    "998813": "Transport of goods by air",
    "998814": "Transport of goods by water",
    "998815": "Courier and logistics services",
    "998816": "Warehousing and storage services",
    "998911": "Security services",
    "998912": "Cleaning services",
    "998913": "Packaging services",
}


def lookup_sac(sac: str) -> Optional[str]:
    sac = sac.strip()
    if sac in SAC_SERVICES:
        return SAC_SERVICES[sac]
    if sac.startswith("99") and len(sac) == 6:
        return "General services under SAC 99"
    return None


def split_tax(taxable_value: float, tax_rate: float, is_interstate: bool = False) -> dict:
    tax_amount = round(taxable_value * tax_rate / 100, 2)
    if is_interstate:
        return {
            "igst": tax_amount,
            "cgst": 0.0,
            "sgst": 0.0,
            "total_tax": tax_amount,
        }
    half = round(tax_amount / 2, 2)
    cgst = half
    sgst = tax_amount - half
    return {
        "igst": 0.0,
        "cgst": cgst,
        "sgst": sgst,
        "total_tax": tax_amount,
    }


def format_inr(amount: float) -> str:
    if amount < 0:
        return f"-{format_inr(-amount)}"
    amount_str = f"{amount:.2f}"
    parts = amount_str.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]
    if len(integer_part) <= 3:
        return f"₹{integer_part}.{decimal_part}"
    last_three = integer_part[-3:]
    rest = integer_part[:-3]
    rest_with_commas = ""
    while len(rest) > 2:
        rest_with_commas = f",{rest[-2:]}{rest_with_commas}"
        rest = rest[:-2]
    if rest:
        rest_with_commas = f"{rest}{rest_with_commas}"
    else:
        rest_with_commas = rest_with_commas.lstrip(",")
    return f"₹{rest_with_commas},{last_three}.{decimal_part}"


def parse_currency(value: str) -> Optional[float]:
    cleaned = value.replace("₹", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def calculate_tax_from_rate(rate: float) -> dict:
    if rate <= 0:
        return {"cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    if rate == 0:
        return {"cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    if rate == 3:
        return {"cgst": 1.5, "sgst": 1.5, "igst": 0.0}
    if rate == 5:
        return {"cgst": 2.5, "sgst": 2.5, "igst": 0.0}
    if rate == 12:
        return {"cgst": 6.0, "sgst": 6.0, "igst": 0.0}
    if rate == 18:
        return {"cgst": 9.0, "sgst": 9.0, "igst": 0.0}
    if rate == 28:
        return {"cgst": 14.0, "sgst": 14.0, "igst": 0.0}
    half = rate / 2
    return {"cgst": half, "sgst": half, "igst": 0.0}
