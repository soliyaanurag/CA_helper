"""Amounts in the Indian number format, for texts shown to people.

    format_inr(Decimal("4500000"))  "₹45,00,000"
    format_inr(20000000)            "₹2,00,00,000"

The last three digits are one group, the rest are grouped in twos (lakh, crore).
Whole rupees only (rounded). The frontend does the same with formatRupees().
"""

from decimal import ROUND_HALF_UP, Decimal


def format_inr(amount) -> str:
    digits = str(int(Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])
