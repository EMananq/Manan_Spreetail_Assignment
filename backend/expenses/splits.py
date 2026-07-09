"""
Split Calculation Engine for FairSplit.

Supports 4 split types:
- equal: Divide evenly among participants, rounding remainder to first person
- unequal: Fixed amounts per person
- percentage: Percentage-based (with auto-normalization if sum != 100%)
- share: Ratio-based (e.g., 1:2:1:2)

Currency conversion: USD → INR at ₹95/USD (static rate per project requirements).
"""

from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings


def convert_to_inr(amount, currency):
    """
    Convert an amount to INR.
    USD is converted at the static rate (₹95/USD).
    INR amounts are returned unchanged.
    """
    if currency.upper() == 'USD':
        return Decimal(str(amount)) * Decimal(str(settings.USD_TO_INR_RATE))
    return Decimal(str(amount))


def round_money(amount):
    """Round to 2 decimal places using standard half-up rounding."""
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_split(total_amount, split_type, participants, split_details=None):
    """
    Calculate how an expense should be split among participants.

    Args:
        total_amount: Total expense amount (Decimal or float)
        split_type: One of 'equal', 'unequal', 'percentage', 'share'
        participants: List of participant identifiers (user IDs or names)
        split_details: Dict mapping participant → value (for unequal/percentage/share)

    Returns:
        List of dicts: [{'participant': id, 'amount': Decimal, 'percentage': float, 'share_value': float}]

    Guarantees: The sum of all split amounts equals exactly total_amount (rounding-safe).
    """
    total = Decimal(str(total_amount))
    results = []

    if split_type == 'equal':
        results = _split_equal(total, participants)

    elif split_type == 'unequal':
        results = _split_unequal(total, participants, split_details or {})

    elif split_type == 'percentage':
        results = _split_percentage(total, participants, split_details or {})

    elif split_type == 'share':
        results = _split_share(total, participants, split_details or {})

    else:
        raise ValueError(f"Unknown split type: {split_type}")

    return results


def _split_equal(total, participants):
    """
    Split equally. Rounding remainder goes to first participant.
    Example: ₹1000 / 3 = ₹333.34, ₹333.33, ₹333.33
    """
    n = len(participants)
    if n == 0:
        return []

    per_person = round_money(total / n)
    results = []

    for i, p in enumerate(participants):
        results.append({
            'participant': p,
            'amount': per_person,
            'percentage': None,
            'share_value': None,
        })

    # Adjust first person for rounding difference
    current_sum = per_person * n
    diff = total - current_sum
    if diff != 0:
        results[0]['amount'] = round_money(results[0]['amount'] + diff)

    return results


def _split_unequal(total, participants, details):
    """
    Split by fixed amounts per person.
    If amounts don't sum to total, adjusts proportionally.
    """
    results = []
    detail_sum = sum(Decimal(str(details.get(str(p), 0))) for p in participants)

    for p in participants:
        raw_amount = Decimal(str(details.get(str(p), 0)))
        if detail_sum != 0 and detail_sum != total:
            # Scale proportionally to match total
            raw_amount = round_money(raw_amount * total / detail_sum)
        results.append({
            'participant': p,
            'amount': round_money(raw_amount),
            'percentage': None,
            'share_value': None,
        })

    # Ensure sum matches total
    current_sum = sum(r['amount'] for r in results)
    diff = total - current_sum
    if diff != 0 and results:
        results[0]['amount'] = round_money(results[0]['amount'] + diff)

    return results


def _split_percentage(total, participants, details):
    """
    Split by percentage. Auto-normalizes if percentages don't sum to 100%.
    Example: 30+30+30+20 = 110% → normalized to 27.27+27.27+27.27+18.18
    """
    pct_sum = sum(Decimal(str(details.get(str(p), 0))) for p in participants)

    if pct_sum == 0:
        # Fall back to equal split
        return _split_equal(total, participants)

    results = []
    for p in participants:
        raw_pct = Decimal(str(details.get(str(p), 0)))
        # Normalize: actual_pct = raw_pct / pct_sum * 100
        normalized_pct = round_money(raw_pct / pct_sum * 100)
        amount = round_money(total * raw_pct / pct_sum)
        results.append({
            'participant': p,
            'amount': amount,
            'percentage': float(normalized_pct),
            'share_value': None,
        })

    # Ensure sum matches total
    current_sum = sum(r['amount'] for r in results)
    diff = total - current_sum
    if diff != 0 and results:
        results[0]['amount'] = round_money(results[0]['amount'] + diff)

    return results


def _split_share(total, participants, details):
    """
    Split by ratio shares.
    Example: 1:2:1:2 → ₹3600 splits as 600, 1200, 600, 1200
    """
    share_sum = sum(Decimal(str(details.get(str(p), 1))) for p in participants)

    if share_sum == 0:
        return _split_equal(total, participants)

    results = []
    for p in participants:
        share = Decimal(str(details.get(str(p), 1)))
        amount = round_money(total * share / share_sum)
        results.append({
            'participant': p,
            'amount': amount,
            'percentage': None,
            'share_value': float(share),
        })

    # Ensure sum matches total
    current_sum = sum(r['amount'] for r in results)
    diff = total - current_sum
    if diff != 0 and results:
        results[0]['amount'] = round_money(results[0]['amount'] + diff)

    return results
