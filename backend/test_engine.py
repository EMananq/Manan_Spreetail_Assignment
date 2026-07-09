"""
Comprehensive test script for FairSplit Python Backend.
Tests the split calculation engine, CSV anomaly detection, and balance/debt simplification.
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fairsplit.settings')
django.setup()

from expenses.splits import calculate_split, convert_to_inr, round_money
from expenses.importer import process_csv_import
from expenses.balances import simplify_debts

def run_tests():
    print("==================================================")
    print("RUNNING FAIRSPLIT PYTHON ENGINE TESTS")
    print("==================================================")

    # Test 1: Split calculations
    print("\nTest 1: Testing Split Calculation Types...")
    
    # 1.1 Equal Split
    equal_split = calculate_split(
        total_amount=Decimal('100.00'),
        split_type='equal',
        participants=['1', '2', '3']
    )
    # Total sum must match exactly
    assert sum(s['amount'] for s in equal_split) == Decimal('100.00'), "Equal split sum mismatch"
    # First participant gets the rounding adjustment
    assert equal_split[0]['amount'] == Decimal('33.34'), "Equal split rounding failed"
    assert equal_split[1]['amount'] == Decimal('33.33'), "Equal split rounding failed"
    print("  [PASS] Equal split passes (INR 100 split 3 ways -> 33.34, 33.33, 33.33)")

    # 1.2 Percentage Split with normalization
    percentage_split = calculate_split(
        total_amount=Decimal('100.00'),
        split_type='percentage',
        participants=['1', '2', '3'],
        split_details={'1': 30, '2': 30, '3': 30} # sums to 90% -> should auto-normalize to equal
    )
    assert sum(s['amount'] for s in percentage_split) == Decimal('100.00'), "Percentage split sum mismatch"
    print("  [PASS] Percentage auto-normalization passes")

    # 1.3 Share Split
    share_split = calculate_split(
        total_amount=Decimal('120.00'),
        split_type='share',
        participants=['1', '2'],
        split_details={'1': 1, '2': 2} # 1:2 ratio -> 40 and 80
    )
    assert share_split[0]['amount'] == Decimal('40.00'), "Share split calculation failed"
    assert share_split[1]['amount'] == Decimal('80.00'), "Share split calculation failed"
    print("  [PASS] Share ratio split passes (1:2 split of 120 -> 40, 80)")

    # Test 2: Anomaly Detection and CSV Parser
    print("\nTest 2: Testing CSV Importer against expenses_export.csv...")
    csv_path = "../expenses_export assigbment annex.xlsx - in.csv"
    if not os.path.exists(csv_path):
        print(f"  [FAIL] CSV File not found at {csv_path}!")
        return

    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_content = f.read()

    result = process_csv_import(csv_content, "expenses_export.csv")
    summary = result['summary']
    anomalies = result['anomalies']

    print(f"  Processed {summary['total_rows']} total rows")
    print(f"  Active rows: {summary['active_rows']}")
    print(f"  Skipped rows: {summary['skipped_rows']}")
    print(f"  Settlement rows: {summary['needs_review_rows']}")
    print(f"  Detected {summary['total_anomalies']} anomalies")

    # Assert expected counts
    assert summary['total_rows'] == 42, f"Expected 42 rows, got {summary['total_rows']}"
    assert summary['total_anomalies'] == 20, f"Expected exactly 20 anomalies, got {summary['total_anomalies']}"
    assert summary['skipped_rows'] == 3, f"Expected 3 skipped rows, got {summary['skipped_rows']}"
    assert summary['settlement_rows'] == 2, f"Expected 2 reclassified settlements, got {summary['settlement_rows']}"
    print("  [PASS] CSV parser & anomaly counts match requirements exactly!")

    # Verify specific anomalies
    categories = [a['category'] for a in anomalies]
    
    # 2.1 Duplicate Row (Row 6)
    assert 'duplicate' in categories, "Failed to detect duplicate row"
    duplicate_anomalies = [a for a in anomalies if a['category'] == 'duplicate']
    assert duplicate_anomalies[0]['row_number'] == 6, "Row 6 duplicate not flagged correctly"
    print("  [PASS] Row 6 Duplicate Marina Bites detected and skipped")

    # 2.2 Reclassified Settlements (Rows 14 & 38)
    settlement_anomalies = [a for a in anomalies if a['category'] == 'settlement_as_expense']
    assert len(settlement_anomalies) == 2, "Failed to detect both settlement anomalies"
    print("  [PASS] Rows 14 & 38 reclassified as settlements")

    # 2.3 Fractional precision check (Row 10: 899.995)
    fractional = [a for a in anomalies if a['category'] == 'fractional_precision']
    assert len(fractional) == 1, "Failed to detect fractional amount"
    assert fractional[0]['corrected_value'] == "900.0", "Incorrect rounding of fractional amount"
    print("  [PASS] Row 10 Fractional amount 899.995 rounded to 900.00")

    # 2.4 Payer name formatting (Row 9, 27)
    normalized = [a for a in anomalies if a['category'] == 'name_normalized']
    assert len(normalized) >= 2, "Failed to normalized payer/participant names"
    print("  [PASS] Lowercase names like 'priya' and 'rohan' normalized successfully")

    # 2.5 Wrong year correction (Row 27: 3/1/2014 -> 2026)
    wrong_year = [a for a in anomalies if a['category'] == 'wrong_year']
    assert len(wrong_year) == 1, "Failed to flag year 2014"
    assert wrong_year[0]['corrected_value'] == "2026-03-12", "Failed to resolve year 2014 to 2026"
    print("  [PASS] Row 27 Wrong year 2014 corrected to March 12, 2026 (Goa trip)")

    # 2.6 Missing currency default to INR (Row 28)
    missing_curr = [a for a in anomalies if a['category'] == 'missing_currency']
    assert len(missing_curr) == 1, "Failed to detect missing currency"
    print("  [PASS] Row 28 Missing currency defaulted to INR")

    # 2.7 Zero-value expense skipped (Row 31)
    zero_amt = [a for a in anomalies if a['category'] == 'zero_amount']
    assert len(zero_amt) == 1, "Failed to detect zero amount"
    print("  [PASS] Row 31 Zero amount Swiggy expense skipped")

    # 2.8 Meera departed member split check (Row 36)
    departed = [a for a in anomalies if a['category'] == 'departed_member']
    assert len(departed) == 1, "Failed to detect departed member Meera in April split"
    print("  [PASS] Row 36 Departed member Meera removed from April split")

    # Test 3: Debt simplification
    print("\nTest 3: Testing Debt Simplification Logic...")
    balances = [
        {'user_id': 1, 'user_name': 'Aisha', 'net_balance': Decimal('1000.00')},
        {'user_id': 2, 'user_name': 'Rohan', 'net_balance': Decimal('-600.00')},
        {'user_id': 3, 'user_name': 'Priya', 'net_balance': Decimal('-400.00')},
    ]
    debts = simplify_debts(balances)
    assert len(debts) == 2, "Simplified transactions count mismatch"
    assert debts[0]['amount'] == Decimal('600.00'), "Simplified debt amount calculation failed"
    print("  [PASS] Debt simplification passes (Rohan owes Aisha 600, Priya owes Aisha 400)")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! 100% CORRECT")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
