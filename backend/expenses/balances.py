"""
Balance Calculation & Debt Simplification Engine.

Implements:
1. Per-user net balance computation (total paid - total owed)
2. Per-expense drill-down (Rohan's requirement: "show me which expenses make up my balance")
3. Greedy debt simplification (Aisha's requirement: "one number per person, who pays whom")
"""

from decimal import Decimal
from .splits import round_money, convert_to_inr


def calculate_balances(expenses, settlements, members):
    """
    Calculate net balances for all group members.

    Args:
        expenses: QuerySet of Expense objects (with splits prefetched)
        settlements: QuerySet of Settlement objects
        members: Dict of {user_id: user_name}

    Returns:
        List of dicts: [{
            'user_id': int,
            'user_name': str,
            'total_paid': Decimal,
            'total_owed': Decimal,
            'net_balance': Decimal,
            'expense_details': [...]
        }]
    """
    # Initialize balances for all members
    balances = {}
    for user_id, user_name in members.items():
        balances[user_id] = {
            'user_id': user_id,
            'user_name': user_name,
            'total_paid': Decimal('0'),
            'total_owed': Decimal('0'),
            'net_balance': Decimal('0'),
            'expense_details': [],
        }

    # Process each expense
    for expense in expenses:
        if expense.status not in ('active',):
            continue

        amount_inr = convert_to_inr(expense.amount, expense.currency)
        payer_id = expense.paid_by_id

        # Credit the payer
        if payer_id in balances:
            balances[payer_id]['total_paid'] += amount_inr

        # Debit each person in the split
        for split in expense.splits.all():
            split_amount_inr = convert_to_inr(split.amount, expense.currency)
            if split.user_id in balances:
                balances[split.user_id]['total_owed'] += split_amount_inr
                balances[split.user_id]['expense_details'].append({
                    'expense_id': expense.id,
                    'description': expense.description,
                    'date': str(expense.expense_date),
                    'total_amount': float(amount_inr),
                    'your_share': float(split_amount_inr),
                    'paid_by': expense.paid_by.name if expense.paid_by else 'Unknown',
                    'currency': expense.currency,
                    'original_amount': float(expense.amount),
                })

    # Process settlements
    for settlement in settlements:
        amount_inr = convert_to_inr(settlement.amount, settlement.currency)

        if settlement.from_user_id in balances:
            balances[settlement.from_user_id]['total_paid'] += amount_inr
        if settlement.to_user_id in balances:
            balances[settlement.to_user_id]['total_owed'] += amount_inr

    # Calculate net balances
    for user_id in balances:
        b = balances[user_id]
        b['net_balance'] = round_money(b['total_paid'] - b['total_owed'])
        b['total_paid'] = round_money(b['total_paid'])
        b['total_owed'] = round_money(b['total_owed'])

    return list(balances.values())


def simplify_debts(balances):
    """
    Greedy debt simplification algorithm.

    Takes net balances and produces the minimum set of transactions
    to settle all debts.

    Algorithm:
    1. Separate into creditors (net_balance > 0) and debtors (net_balance < 0)
    2. Sort creditors descending, debtors ascending (by absolute value)
    3. Match largest debtor with largest creditor for min(debt, credit)
    4. Repeat until all settled

    Args:
        balances: List of balance dicts with 'user_id', 'user_name', 'net_balance'

    Returns:
        List of dicts: [{'from_id': int, 'from_name': str, 'to_id': int, 'to_name': str, 'amount': Decimal}]
    """
    # Separate creditors and debtors
    creditors = []
    debtors = []

    for b in balances:
        net = Decimal(str(b['net_balance']))
        if net > Decimal('0.01'):
            creditors.append({
                'user_id': b['user_id'],
                'user_name': b['user_name'],
                'amount': net,
            })
        elif net < Decimal('-0.01'):
            debtors.append({
                'user_id': b['user_id'],
                'user_name': b['user_name'],
                'amount': abs(net),
            })

    # Sort: largest amounts first
    creditors.sort(key=lambda x: x['amount'], reverse=True)
    debtors.sort(key=lambda x: x['amount'], reverse=True)

    transactions = []
    i, j = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        settle_amount = min(debtor['amount'], creditor['amount'])

        if settle_amount > Decimal('0.01'):
            transactions.append({
                'from_id': debtor['user_id'],
                'from_name': debtor['user_name'],
                'to_id': creditor['user_id'],
                'to_name': creditor['user_name'],
                'amount': round_money(settle_amount),
            })

        debtor['amount'] -= settle_amount
        creditor['amount'] -= settle_amount

        if debtor['amount'] < Decimal('0.01'):
            i += 1
        if creditor['amount'] < Decimal('0.01'):
            j += 1

    return transactions
