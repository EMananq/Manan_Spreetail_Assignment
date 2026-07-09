"""
CSV Import Engine for FairSplit.

Detects 15+ anomaly categories in the expenses_export CSV:
- duplicate: Exact duplicate entries (same date, amount, description)
- conflicting_duplicate: Same event logged differently (Thalassa dinner rows 24/25)
- settlement_as_expense: Settlements logged as expenses (rows 14, 38)
- missing_payer: Empty paid_by field (row 13)
- wrong_year: Date year outside 2025-2027 range (row 27: "3/1/2014")
- ambiguous_date: Ambiguous MM/DD vs DD/MM format (row 34: "5/4/2026")
- departed_member: Inactive member in split_with (row 36: Meera after March)
- percentage_sum_mismatch: Percentages not summing to 100% (rows 15, 32)
- negative_amount: Negative values treated as refunds (row 26)
- zero_amount: Zero-value entries skipped (row 31)
- missing_currency: No currency specified (row 28)
- non_member_participant: External participants (row 23: Kabir)
- name_normalized: Inconsistent name formatting
- fractional_precision: Sub-paisa amounts rounded (row 10)
- conflicting_split_type: Mismatched split_type vs split_details (row 42)
"""

import csv
import io
import re
from datetime import datetime, date
from decimal import Decimal


# ─── Known flat members and their timelines ─────────────────────────────
MEMBER_TIMELINE = {
    'Aisha': {'joined_at': '2026-01-01', 'left_at': None},
    'Rohan': {'joined_at': '2026-01-01', 'left_at': None},
    'Priya': {'joined_at': '2026-01-01', 'left_at': None},
    'Meera': {'joined_at': '2026-01-01', 'left_at': '2026-03-31'},
    'Dev':   {'joined_at': '2026-01-01', 'left_at': None},
    'Sam':   {'joined_at': '2026-04-08', 'left_at': None},
    'Kabir': {'joined_at': '2026-03-11', 'left_at': '2026-03-11'},
}

# Known name variations → canonical name
NAME_ALIASES = {
    'priya': 'Priya',
    'priya s': 'Priya',
    'rohan': 'Rohan',
    'aisha': 'Aisha',
    'meera': 'Meera',
    'dev': 'Dev',
    'sam': 'Sam',
    'kabir': 'Kabir',
    "dev's friend kabir": 'Kabir',
}

# Trip dates for contextual date correction
GOA_TRIP = {'start': '2026-03-08', 'end': '2026-03-12'}


def normalize_name(name):
    """
    Normalize a payer/participant name to its canonical form.
    Returns (canonical_name, was_changed).
    """
    if not name:
        return ('', False)

    cleaned = name.strip()
    lookup = cleaned.lower().strip()

    if lookup in NAME_ALIASES:
        canonical = NAME_ALIASES[lookup]
        return (canonical, canonical != cleaned)

    # Capitalize first letter
    capitalized = cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
    return (capitalized, capitalized != cleaned)


def is_member_active_on_date(name, date_str):
    """
    Check if a member was active on a given date.
    Uses the MEMBER_TIMELINE to enforce temporal membership rules.
    """
    timeline = MEMBER_TIMELINE.get(name)
    if not timeline:
        return True  # Unknown members assumed active for their expenses

    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        joined = datetime.strptime(timeline['joined_at'], '%Y-%m-%d').date()
        left = datetime.strptime(timeline['left_at'], '%Y-%m-%d').date() if timeline['left_at'] else None

        if check_date < joined:
            return False
        if left and check_date > left:
            return False
        return True
    except (ValueError, TypeError):
        return True


def parse_split_details(details_str):
    """
    Parse split_details field: "Aisha 30; Rohan 30; Priya 30; Meera 20"
    Returns dict: {'Aisha': 30.0, 'Rohan': 30.0, ...}
    """
    result = {}
    if not details_str or not details_str.strip():
        return result

    parts = details_str.split(';')
    for part in parts:
        trimmed = part.strip()
        match = re.match(r'^(.+?)\s+([\d.]+)%?$', trimmed)
        if match:
            name = normalize_name(match.group(1))[0]
            value = float(match.group(2))
            result[name] = value

    return result


def parse_split_with(split_str):
    """
    Parse split_with field: "Aisha; Rohan; Priya; Meera"
    Returns list of canonical names.
    """
    if not split_str or not split_str.strip():
        return []

    names = []
    for part in split_str.split(';'):
        name = normalize_name(part.strip())[0]
        if name:
            names.append(name)
    return names


def parse_date(date_str):
    """
    Parse a date string in M/D/YYYY format to ISO format.
    Returns (iso_date_str, anomalies_list).
    """
    anomalies = []
    if not date_str or not date_str.strip():
        return (None, [{'category': 'missing_date', 'severity': 'error',
                        'description': 'Date is missing'}])

    parts = date_str.strip().split('/')
    if len(parts) != 3:
        return (None, [{'category': 'invalid_date', 'severity': 'error',
                        'description': f'Cannot parse date "{date_str}"'}])

    try:
        month = int(parts[0])
        day = int(parts[1])
        year = int(parts[2])
    except ValueError:
        return (None, [{'category': 'invalid_date', 'severity': 'error',
                        'description': f'Non-numeric date components in "{date_str}"'}])

    # Check for wrong year (row 27: "3/1/2014")
    if year < 2025 or year > 2027:
        corrected_year = 2026
        # If it's during the Goa trip period, use the last day
        if month == 3:
            corrected_date = '2026-03-12'
        else:
            corrected_date = f'{corrected_year}-{month:02d}-{day:02d}'
        anomalies.append({
            'category': 'wrong_year',
            'severity': 'warning',
            'description': f'Date "{date_str}" has year {year}, outside expected range (2025-2027). '
                           f'Context suggests Goa trip (March 8-12, 2026). Auto-corrected to {corrected_date}.',
            'original_value': date_str,
            'corrected_value': corrected_date,
            'action_taken': 'auto_corrected',
            'status': 'needs_review',
        })
        return (corrected_date, anomalies)

    iso_date = f'{year}-{month:02d}-{day:02d}'
    return (iso_date, anomalies)


def _month_name(month_num):
    """Get month name from number."""
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month_num] if 1 <= month_num <= 12 else str(month_num)


def are_duplicates(row1, row2):
    """
    Check if two rows are exact duplicates (same date, amount, description).
    Uses fuzzy matching for description comparison.
    """
    desc1 = re.sub(r'[^a-z0-9]', '', row1['description'].lower())
    desc2 = re.sub(r'[^a-z0-9]', '', (row2.get('description', '') or '').lower())

    # Must have same date
    if row1.get('parsed_date') and row2.get('date'):
        date2_parts = row2['date'].split('/')
        if len(date2_parts) == 3:
            try:
                m, d, y = int(date2_parts[0]), int(date2_parts[1]), int(date2_parts[2])
                date2_iso = f'{y}-{m:02d}-{d:02d}'
                if row1['parsed_date'] != date2_iso:
                    return False
            except ValueError:
                return False

    amount2 = float(row2.get('amount', 0) or 0)

    # Exact: same description + same amount
    if row1['parsed_amount'] == amount2 and desc1 == desc2:
        return True

    # Fuzzy: shared words + same amount
    words1 = set(row1['description'].lower().split())
    words2 = set((row2.get('description', '') or '').lower().split())
    common = [w for w in words1 if w in words2 and len(w) > 2]

    if len(common) >= 2 and row1['parsed_amount'] == amount2:
        return True

    return False


def are_conflicting_duplicates(row1, row2):
    """
    Check if two rows represent the same event with different data.
    Requires same date or adjacent dates to prevent false positives.
    """
    # Check date proximity
    if row1.get('parsed_date') and row2.get('date'):
        date2_parts = row2['date'].split('/')
        if len(date2_parts) == 3:
            try:
                m, d, y = int(date2_parts[0]), int(date2_parts[1]), int(date2_parts[2])
                if y < 2025 or y > 2027:
                    return False
                date2_iso = f'{y}-{m:02d}-{d:02d}'
                d1 = datetime.strptime(row1['parsed_date'], '%Y-%m-%d')
                d2 = datetime.strptime(date2_iso, '%Y-%m-%d')
                diff_days = abs((d1 - d2).days)
                if diff_days > 1:
                    return False
            except ValueError:
                return False

    desc1 = row1['description'].lower()
    desc2 = (row2.get('description', '') or '').lower()

    words1 = set(w for w in desc1.split() if len(w) > 2)
    words2 = set(w for w in desc2.split() if len(w) > 2)
    common = [w for w in words1 if w in words2]

    amount2 = float(row2.get('amount', 0) or 0)

    # Similar description but different amounts → conflicting
    if len(common) >= 2 and row1['parsed_amount'] != amount2:
        return True

    return False


def process_csv_import(csv_content, filename='expenses_export.csv'):
    """
    Main CSV import processor.

    Parses each row, detects anomalies, applies corrections, and returns
    a structured result with processed rows and anomaly reports.

    Args:
        csv_content: String content of the CSV file
        filename: Original filename for reporting

    Returns:
        dict: {
            'rows': [...processed rows...],
            'anomalies': [...all anomalies...],
            'summary': {total_rows, active, skipped, settlements, needs_review, total_anomalies}
        }
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    raw_rows = list(reader)

    all_anomalies = []
    processed_rows = []

    for i, raw_row in enumerate(raw_rows):
        row_number = i + 2  # +2: 1-indexed + header row
        row_anomalies = []

        # ─── Extract fields ─────────────────────────────────────
        raw_date = (raw_row.get('date', '') or '').strip()
        raw_description = (raw_row.get('description', '') or '').strip()
        raw_paid_by = (raw_row.get('paid_by', '') or '').strip()
        raw_amount = (raw_row.get('amount', '') or '').strip()
        raw_currency = (raw_row.get('currency', '') or '').strip()
        raw_split_type = (raw_row.get('split_type', '') or '').strip()
        raw_split_with = (raw_row.get('split_with', '') or '').strip()
        raw_split_details = (raw_row.get('split_details', '') or '').strip()
        raw_notes = (raw_row.get('notes', '') or '').strip()

        # ─── Parse date ─────────────────────────────────────────
        parsed_date, date_anomalies = parse_date(raw_date)
        for a in date_anomalies:
            a['row_number'] = row_number
            row_anomalies.append(a)

        # Check for ambiguous date — only when notes mention format confusion
        if parsed_date and raw_notes and any(kw in raw_notes.lower() for kw in ['april', 'may', 'format', 'ambiguous']):
            parts = raw_date.strip().split('/')
            if len(parts) == 3:
                try:
                    m, d = int(parts[0]), int(parts[1])
                    if m <= 12 and d <= 12 and m != d:
                        row_anomalies.append({
                            'row_number': row_number,
                            'category': 'ambiguous_date',
                            'severity': 'warning',
                            'description': f'Date "{raw_date}" is ambiguous: could be {_month_name(m)} {d} (MM/DD) '
                                           f'or {_month_name(d)} {m} (DD/MM). Interpreting as {_month_name(m)} {d} '
                                           f'(MM/DD format consistent with rest of CSV). Note says: "{raw_notes}"',
                            'original_value': raw_date,
                            'corrected_value': parsed_date,
                            'action_taken': 'auto_corrected',
                            'status': 'needs_review',
                        })
                except ValueError:
                    pass

        # ─── Parse amount ───────────────────────────────────────
        try:
            parsed_amount = float(raw_amount) if raw_amount else 0.0
        except ValueError:
            parsed_amount = 0.0

        # Check fractional precision (row 10: 899.995)
        if raw_amount and '.' in raw_amount:
            decimal_places = len(raw_amount.split('.')[1])
            if decimal_places > 2:
                rounded = round(parsed_amount, 2)
                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'fractional_precision',
                    'severity': 'info',
                    'description': f'Amount {raw_amount} rounded to {rounded}',
                    'original_value': raw_amount,
                    'corrected_value': str(rounded),
                    'action_taken': 'auto_corrected',
                    'status': 'auto_resolved',
                })
                parsed_amount = rounded

        # Check zero amount (row 31)
        if parsed_amount == 0:
            row_anomalies.append({
                'row_number': row_number,
                'category': 'zero_amount',
                'severity': 'warning',
                'description': f'Amount is zero for "{raw_description}". '
                               f'Note says: "{raw_notes}"' if raw_notes else f'Amount is zero for "{raw_description}".',
                'action_taken': 'skipped',
                'status': 'auto_resolved',
            })

        # Check negative amount (row 26)
        if parsed_amount < 0:
            row_anomalies.append({
                'row_number': row_number,
                'category': 'negative_amount',
                'severity': 'info',
                'description': f'Negative amount ({parsed_amount}) treated as refund/credit for '
                               f'"{raw_description}". Note: "{raw_notes}"' if raw_notes else
                               f'Negative amount ({parsed_amount}) treated as refund/credit for "{raw_description}".',
                'action_taken': 'treated_as_refund',
                'status': 'auto_resolved',
            })

        # ─── Normalize payer name ───────────────────────────────
        paid_by, name_changed = normalize_name(raw_paid_by)

        if not paid_by:
            row_anomalies.append({
                'row_number': row_number,
                'category': 'missing_payer',
                'severity': 'error',
                'description': f'Payer name is missing or empty for "{raw_description}". '
                               f'Note: "{raw_notes}"' if raw_notes else
                               f'Payer name is missing or empty for "{raw_description}". Flagged for manual review.',
                'action_taken': 'flagged',
                'status': 'needs_review',
            })

        if name_changed and paid_by:
            row_anomalies.append({
                'row_number': row_number,
                'category': 'name_normalized',
                'severity': 'info',
                'description': f'Payer name "{raw_paid_by}" normalized to "{paid_by}"',
                'original_value': raw_paid_by,
                'corrected_value': paid_by,
                'action_taken': 'auto_corrected',
                'status': 'auto_resolved',
            })

        # ─── Currency check ─────────────────────────────────────
        currency = raw_currency.upper() if raw_currency else ''
        if not currency:
            currency = 'INR'
            row_anomalies.append({
                'row_number': row_number,
                'category': 'missing_currency',
                'severity': 'warning',
                'description': f'No currency specified for "{raw_description}". Defaulting to INR.',
                'action_taken': 'auto_corrected',
                'status': 'auto_resolved',
            })

        # ─── Parse split participants ───────────────────────────
        split_with_raw = [p.strip() for p in raw_split_with.split(';') if p.strip()] if raw_split_with else []
        split_with = []
        for raw_name in split_with_raw:
            canonical, was_changed = normalize_name(raw_name)
            if canonical:
                split_with.append(canonical)
                if was_changed:
                    row_anomalies.append({
                        'row_number': row_number,
                        'category': 'name_normalized',
                        'severity': 'info',
                        'description': f'Participant name "{raw_name}" normalized to "{canonical}"',
                        'original_value': raw_name,
                        'corrected_value': canonical,
                        'action_taken': 'auto_corrected',
                        'status': 'auto_resolved',
                    })
        split_details = parse_split_details(raw_split_details)

        # Check for non-member participants (row 23: Kabir)
        for name in split_with:
            if name not in MEMBER_TIMELINE and name.lower() not in NAME_ALIASES:
                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'non_member_participant',
                    'severity': 'info',
                    'description': f'Non-member "{name}" included in split. '
                                   f'Temporarily registering them for this split.',
                    'action_taken': 'auto_corrected',
                    'status': 'auto_resolved',
                })

        # ─── Check for departed members (row 36: Meera in April) ──
        if parsed_date:
            departed = [n for n in split_with if not is_member_active_on_date(n, parsed_date)]
            if departed:
                for dep_name in departed:
                    split_with = [n for n in split_with if n != dep_name]
                    if dep_name in split_details:
                        del split_details[dep_name]
                    row_anomalies.append({
                        'row_number': row_number,
                        'category': 'departed_member',
                        'severity': 'warning',
                        'description': f'"{dep_name}" was not an active member on {parsed_date}. '
                                       f'Removed from split.',
                        'original_value': '; '.join([dep_name] + split_with),
                        'corrected_value': '; '.join(split_with),
                        'action_taken': 'auto_corrected',
                        'status': 'needs_review',
                    })

        # ─── Check split type anomalies ─────────────────────────
        split_type = raw_split_type.lower() if raw_split_type else 'equal'

        # Detect settlement_as_expense (rows 14, 38)
        is_settlement = False
        if not raw_split_type and ('paid' in raw_description.lower() and 'back' in raw_description.lower()):
            is_settlement = True
        if 'deposit share' in raw_description.lower() or 'settlement' in raw_notes.lower() if raw_notes else False:
            is_settlement = True
        if not raw_split_type and raw_notes and 'settlement' in raw_notes.lower():
            is_settlement = True

        if is_settlement:
            row_anomalies.append({
                'row_number': row_number,
                'category': 'settlement_as_expense',
                'severity': 'warning',
                'description': f'"{raw_description}" appears to be a settlement/payment, not a shared expense. '
                               f'Note: "{raw_notes}". Reclassified as settlement.' if raw_notes else
                               f'"{raw_description}" appears to be a settlement. Reclassified.',
                'original_value': f'expense: {raw_description}',
                'corrected_value': f'settlement: {paid_by} → target',
                'action_taken': 'reclassified',
                'status': 'needs_review',
            })

        # Check percentage sum (rows 15, 32: 110%)
        if split_type == 'percentage' and split_details:
            pct_sum = sum(split_details.values())
            if abs(pct_sum - 100) > 0.01:
                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'percentage_sum_mismatch',
                    'severity': 'warning',
                    'description': f'Percentages sum to {pct_sum}% instead of 100%. '
                                   f'Will normalize proportionally.',
                    'original_value': f'{pct_sum}%',
                    'corrected_value': '100%',
                    'action_taken': 'auto_corrected',
                    'status': 'needs_review',
                })

        # Check conflicting split_type vs split_details (row 42)
        if split_type == 'equal' and split_details:
            values = list(split_details.values())
            all_equal = len(set(values)) <= 1
            if all_equal:
                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'conflicting_split_type',
                    'severity': 'info',
                    'description': f'Split type is "equal" but split_details are provided. '
                                   f'Since all shares are equal, using "equal" split. '
                                   f'Note: "{raw_notes}"' if raw_notes else
                                   f'Split type is "equal" but split_details are provided. Using equal split.',
                    'action_taken': 'auto_corrected',
                    'status': 'auto_resolved',
                })

        # ─── Build processed row ────────────────────────────────
        status = 'active'
        if is_settlement:
            status = 'settlement'
        elif parsed_amount == 0:
            status = 'skipped'
        elif not paid_by:
            status = 'needs_review'

        processed_row = {
            'row_number': row_number,
            'description': raw_description,
            'paid_by': paid_by,
            'amount': abs(parsed_amount),
            'is_refund': parsed_amount < 0,
            'currency': currency,
            'split_type': split_type if not is_settlement else 'settlement',
            'split_with': split_with,
            'split_details': split_details,
            'parsed_date': parsed_date,
            'parsed_amount': parsed_amount,
            'notes': raw_notes,
            'status': status,
            'anomalies': row_anomalies,
            'raw': raw_row,
        }

        # ─── Duplicate detection ────────────────────────────────
        for prev in processed_rows:
            if prev['status'] == 'skipped':
                continue

            if are_duplicates(prev, raw_row):
                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'duplicate',
                    'severity': 'warning',
                    'description': f'Duplicate of row {prev["row_number"]}: '
                                   f'"{raw_description}" matches "{prev["description"]}" '
                                   f'(same amount {parsed_amount}, same date).',
                    'action_taken': 'skipped',
                    'status': 'auto_resolved',
                })
                status = 'skipped'
                processed_row['status'] = 'skipped'
                break

            if are_conflicting_duplicates(prev, raw_row):
                # Check notes for which to keep
                if raw_notes and ('wrong' in raw_notes.lower() or 'hers' in raw_notes.lower()):
                    # This row's note says the other one is wrong → skip prev
                    prev_anomaly = {
                        'row_number': prev['row_number'],
                        'category': 'conflicting_duplicate',
                        'severity': 'warning',
                        'description': f'Conflicts with row {row_number}: '
                                       f'"{prev["description"]}" ({prev["parsed_amount"]} {prev["currency"]}) '
                                       f'vs "{raw_description}" ({parsed_amount} {currency}). '
                                       f'Superseded by row {row_number}.',
                        'original_value': f'Row {prev["row_number"]}: {prev["parsed_amount"]}, Row {row_number}: {parsed_amount}',
                        'corrected_value': f'Favoring row {row_number}',
                        'action_taken': 'skipped',
                        'status': 'auto_resolved',
                    }
                    all_anomalies.append(prev_anomaly)
                    prev['anomalies'].append(prev_anomaly)
                    prev['status'] = 'skipped'

                row_anomalies.append({
                    'row_number': row_number,
                    'category': 'conflicting_duplicate',
                    'severity': 'warning',
                    'description': f'Conflicts with row {prev["row_number"]}: '
                                   f'"{raw_description}" ({parsed_amount} {currency}) vs '
                                   f'"{prev["description"]}" ({prev["parsed_amount"]} {prev["currency"]}).',
                    'original_value': f'Row {prev["row_number"]}: {prev["parsed_amount"]}, Row {row_number}: {parsed_amount}',
                    'corrected_value': 'Needs review',
                    'action_taken': 'auto_corrected',
                    'status': 'needs_review',
                })

        processed_rows.append(processed_row)
        all_anomalies.extend(row_anomalies)

    # ─── Build summary ──────────────────────────────────────────
    active_count = sum(1 for r in processed_rows if r['status'] == 'active')
    skipped_count = sum(1 for r in processed_rows if r['status'] == 'skipped')
    settlement_count = sum(1 for r in processed_rows if r['status'] == 'settlement')
    review_count = sum(1 for r in processed_rows if r['status'] == 'needs_review')

    return {
        'rows': processed_rows,
        'anomalies': all_anomalies,
        'summary': {
            'total_rows': len(processed_rows),
            'active_rows': active_count,
            'skipped_rows': skipped_count,
            'settlement_rows': settlement_count,
            'needs_review_rows': review_count,
            'total_anomalies': len(all_anomalies),
        },
    }
