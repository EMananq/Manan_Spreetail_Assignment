"""
Django REST Framework API Views for FairSplit.

Endpoints:
- POST /api/auth/register/ — Register new user
- POST /api/auth/login/ — Login and receive JWT
- GET  /api/auth/me/ — Current user info

- GET/POST    /api/groups/ — List/Create groups
- GET/PUT/DEL /api/groups/<id>/ — Group detail
- GET/POST    /api/groups/<id>/members/ — Manage memberships
- GET/POST    /api/groups/<id>/expenses/ — List/Create expenses
- GET/POST    /api/groups/<id>/settlements/ — List/Create settlements
- GET         /api/groups/<id>/balances/ — Compute balances & simplified debts
- POST        /api/groups/<id>/import/ — Import CSV data
- GET         /api/groups/<id>/import-reports/ — List import reports
"""

from decimal import Decimal
from datetime import date as date_type

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    User, Group, GroupMembership, Expense,
    ExpenseSplit, Settlement, ImportReport, ImportAnomaly,
)
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    GroupSerializer, GroupCreateSerializer,
    GroupMembershipSerializer,
    ExpenseSerializer, ExpenseCreateSerializer,
    ExpenseSplitSerializer,
    SettlementSerializer, SettlementCreateSerializer,
    ImportReportSerializer,
)
from .authentication import generate_token
from .splits import calculate_split, convert_to_inr, round_money
from .balances import calculate_balances, simplify_debts
from .importer import process_csv_import


# ═══════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user account."""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data['email']
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        email=email,
        name=serializer.validated_data['name'],
        password=serializer.validated_data['password'],
    )
    token = generate_token(user)

    return Response({
        'token': token,
        'user': UserSerializer(user).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login with email and password, receive JWT."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user = User.objects.get(email=serializer.validated_data['email'])
    except User.DoesNotExist:
        return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(serializer.validated_data['password']):
        return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

    token = generate_token(user)
    return Response({
        'token': token,
        'user': UserSerializer(user).data,
    })


@api_view(['GET'])
def me(request):
    """Get current authenticated user info."""
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
def users_list(request):
    """List all users (for adding members to groups)."""
    users = User.objects.all().order_by('name')
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════════
# GROUP ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def groups_list(request):
    """List user's groups or create a new group."""
    if request.method == 'GET':
        show_all = request.query_params.get('all', 'false').lower() == 'true'
        if show_all:
            groups = Group.objects.all()
        else:
            groups = Group.objects.filter(memberships__user=request.user)
        serializer = GroupSerializer(groups.distinct(), many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = Group.objects.create(
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description', ''),
            default_currency=serializer.validated_data.get('default_currency', 'INR'),
        )
        # Add creator as admin member
        GroupMembership.objects.create(
            group=group,
            user=request.user,
            joined_at=date_type.today(),
            role='admin',
        )
        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
def group_detail(request, group_id):
    """Get, update, or delete a specific group."""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(GroupSerializer(group).data)

    elif request.method == 'PUT':
        group.name = request.data.get('name', group.name)
        group.description = request.data.get('description', group.description)
        group.save()
        return Response(GroupSerializer(group).data)

    elif request.method == 'DELETE':
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════
# MEMBERSHIP ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def group_members(request, group_id):
    """List or add group members."""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        memberships = group.memberships.select_related('user').all()
        serializer = GroupMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        user_id = request.data.get('user_id')
        joined_at = request.data.get('joined_at', str(date_type.today()))
        role = request.data.get('role', 'member')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.create(
            group=group,
            user=user,
            joined_at=joined_at,
            role=role,
        )
        return Response(GroupMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
def update_membership(request, group_id, membership_id):
    """Update a membership (e.g., set left_at date)."""
    try:
        membership = GroupMembership.objects.get(id=membership_id, group_id=group_id)
    except GroupMembership.DoesNotExist:
        return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)

    if 'left_at' in request.data:
        membership.left_at = request.data['left_at']
    if 'role' in request.data:
        membership.role = request.data['role']
    membership.save()
    return Response(GroupMembershipSerializer(membership).data)


# ═══════════════════════════════════════════════════════════════════════
# EXPENSE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def group_expenses(request, group_id):
    """List or create expenses for a group."""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        expenses = group.expenses.select_related('paid_by').prefetch_related('splits__user').all()
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Use paid_by_id from request if provided, else fall back to current user
        paid_by_id = data.get('paid_by_id') or request.data.get('paid_by_id')
        if paid_by_id:
            try:
                payer = User.objects.get(id=int(paid_by_id))
            except User.DoesNotExist:
                return Response({'error': 'Payer user not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            payer = request.user

        expense = Expense.objects.create(
            group=group,
            paid_by=payer,
            description=data['description'],
            amount=data['amount'],
            currency=data.get('currency', 'INR'),
            split_type=data['split_type'],
            expense_date=data['expense_date'],
            notes=data.get('notes', ''),
        )

        # Calculate splits
        splits = calculate_split(
            total_amount=float(expense.amount),
            split_type=expense.split_type,
            participants=[str(uid) for uid in data['split_with']],
            split_details={str(k): v for k, v in data.get('split_details', {}).items()},
        )

        for split_data in splits:
            user_id = int(split_data['participant'])
            ExpenseSplit.objects.create(
                expense=expense,
                user_id=user_id,
                amount=split_data['amount'],
                share_value=split_data.get('share_value'),
                percentage=split_data.get('percentage'),
            )

        return Response(
            ExpenseSerializer(expense).data,
            status=status.HTTP_201_CREATED,
        )


# ═══════════════════════════════════════════════════════════════════════
# SETTLEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def group_settlements(request, group_id):
    """List or create settlements for a group."""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        settlements = group.settlements.select_related('from_user', 'to_user').all()
        serializer = SettlementSerializer(settlements, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Use from_user_id from request if provided, else fall back to current user
        from_user_id = data.get('from_user_id') or request.data.get('from_user_id')
        if from_user_id:
            try:
                from_user = User.objects.get(id=int(from_user_id))
            except User.DoesNotExist:
                return Response({'error': 'From user not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            from_user = request.user

        settlement = Settlement.objects.create(
            group=group,
            from_user=from_user,
            to_user_id=data['to_user_id'],
            amount=data['amount'],
            currency=data.get('currency', 'INR'),
            settlement_date=data['settlement_date'],
            notes=data.get('notes', ''),
        )

        return Response(
            SettlementSerializer(settlement).data,
            status=status.HTTP_201_CREATED,
        )


# ═══════════════════════════════════════════════════════════════════════
# BALANCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def group_balances(request, group_id):
    """
    Compute group balances, individual summaries, and simplified debts.
    This is the core endpoint that answers:
    - Aisha: "Who pays whom, how much"
    - Rohan: "Which expenses make up my balance"
    """
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get all active memberships
    memberships = group.memberships.select_related('user').all()
    members = {m.user_id: m.user.name for m in memberships}

    # Get expenses and settlements
    expenses = group.expenses.filter(
        status='active'
    ).select_related('paid_by').prefetch_related('splits__user')

    settlements = group.settlements.select_related('from_user', 'to_user')

    # Calculate balances
    balances = calculate_balances(expenses, settlements, members)

    # Simplify debts
    debts = simplify_debts(balances)

    # Convert Decimal to float for JSON
    for b in balances:
        b['total_paid'] = float(b['total_paid'])
        b['total_owed'] = float(b['total_owed'])
        b['net_balance'] = float(b['net_balance'])

    for d in debts:
        d['amount'] = float(d['amount'])

    return Response({
        'balances': balances,
        'simplified_debts': debts,
        'member_count': len(members),
    })


# ═══════════════════════════════════════════════════════════════════════
# IMPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['POST'])
def import_csv(request, group_id):
    """
    Import CSV expenses into a group.

    Accepts either:
    - action=preview: Parse and detect anomalies without importing
    - action=import: Parse, detect, and persist to database
    """
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    action = request.data.get('action', 'preview')
    csv_file = request.FILES.get('file')
    csv_content = request.data.get('csv_content', '')

    # Ensure csv_content is a string (DRF may parse JSON body differently)
    if isinstance(csv_content, (dict, list)):
        return Response({'error': 'csv_content must be a string'}, status=status.HTTP_400_BAD_REQUEST)
    csv_content = str(csv_content) if csv_content else ''

    if csv_file:
        csv_content = csv_file.read().decode('utf-8')
    elif not csv_content:
        return Response({'error': 'No CSV data provided'}, status=status.HTTP_400_BAD_REQUEST)

    filename = csv_file.name if csv_file else 'expenses_export.csv'

    # Process the CSV
    result = process_csv_import(csv_content, filename)

    if action == 'preview':
        return Response({
            'action': 'preview',
            'rows': result['rows'],
            'anomalies': result['anomalies'],
            'summary': result['summary'],
        })

    # ─── action == 'import': persist to database ────────────────
    # Create import report
    report = ImportReport.objects.create(
        group=group,
        filename=filename,
        total_rows=result['summary']['total_rows'],
    )

    imported = 0
    skipped = 0
    errors = 0

    # Build user lookup by name
    user_lookup = {}
    for m in group.memberships.select_related('user').all():
        user_lookup[m.user.name.lower()] = m.user

    # GAP 5 FIX: Read payer assignments from frontend
    payer_assignments = request.data.get('payer_assignments', {})
    # Convert keys to int if needed (JSON may send string keys)
    payer_assignments = {int(k): v for k, v in payer_assignments.items()} if payer_assignments else {}

    for row in result['rows']:
        # Save anomalies
        for anomaly in row['anomalies']:
            ImportAnomaly.objects.create(
                import_report=report,
                row_number=anomaly['row_number'],
                severity=anomaly.get('severity', 'info'),
                category=anomaly['category'],
                description=anomaly['description'],
                original_value=anomaly.get('original_value'),
                corrected_value=anomaly.get('corrected_value'),
                action_taken=anomaly.get('action_taken', 'flagged'),
                status=anomaly.get('status', 'auto_resolved'),
            )

        if row['status'] == 'skipped':
            skipped += 1
            continue

        # GAP 5 FIX: If user assigned a payer for this row, apply it
        if row['status'] == 'needs_review' and not row['paid_by']:
            assigned_payer = payer_assignments.get(row['row_number'])
            if assigned_payer:
                row['paid_by'] = assigned_payer
                row['status'] = 'active'
            else:
                errors += 1
                continue

        # Look up or create payer
        payer = user_lookup.get(row['paid_by'].lower())
        if not payer and row['paid_by']:
            # Create the user if not found
            payer = User.objects.create_user(
                email=f"{row['paid_by'].lower()}@flat.app",
                name=row['paid_by'],
                password='password123',
            )
            user_lookup[row['paid_by'].lower()] = payer
            # Add to group
            GroupMembership.objects.get_or_create(
                group=group,
                user=payer,
                defaults={
                    'joined_at': row['parsed_date'] or '2026-01-01',
                    'role': 'member',
                },
            )

        if row['status'] == 'settlement':
            # Find the target user for settlement
            # Parse from description or default to first split_with member
            target_name = None
            if row['split_with']:
                target_name = row['split_with'][0]
            elif 'aisha' in row['description'].lower():
                target_name = 'Aisha'

            target = user_lookup.get((target_name or '').lower())
            if payer and target:
                Settlement.objects.create(
                    group=group,
                    from_user=payer,
                    to_user=target,
                    amount=Decimal(str(row['amount'])),
                    currency=row['currency'],
                    settlement_date=row['parsed_date'] or '2026-01-01',
                    notes=row['notes'],
                    import_row_number=row['row_number'],
                )
                imported += 1
            continue

        # Create expense
        if payer and row['parsed_date']:
            expense = Expense.objects.create(
                group=group,
                paid_by=payer,
                description=row['description'],
                amount=Decimal(str(row['amount'])) * (Decimal('-1') if row.get('is_refund') else Decimal('1')),
                currency=row['currency'],
                split_type=row['split_type'] if row['split_type'] != 'settlement' else 'equal',
                expense_date=row['parsed_date'],
                notes=row['notes'],
                status=row['status'],
                import_row_number=row['row_number'],
            )

            # Calculate and create splits
            participants = row['split_with']
            if not participants and payer:
                # Default: split with all active members on that date
                participants = [
                    m.user.name for m in group.memberships.select_related('user').all()
                    if not m.left_at or str(m.left_at) >= row['parsed_date']
                ]

            # Map names to user IDs for split calculation
            participant_ids = []
            for name in participants:
                user = user_lookup.get(name.lower())
                if user:
                    participant_ids.append(str(user.id))

            if participant_ids:
                split_details = {}
                for name, value in row.get('split_details', {}).items():
                    user = user_lookup.get(name.lower())
                    if user:
                        split_details[str(user.id)] = value

                splits = calculate_split(
                    total_amount=float(expense.amount),
                    split_type=row['split_type'] if row['split_type'] != 'settlement' else 'equal',
                    participants=participant_ids,
                    split_details=split_details if split_details else None,
                )

                for s in splits:
                    ExpenseSplit.objects.create(
                        expense=expense,
                        user_id=int(s['participant']),
                        amount=s['amount'],
                        share_value=s.get('share_value'),
                        percentage=s.get('percentage'),
                    )

            imported += 1

    # Update report counts
    report.imported_count = imported
    report.skipped_count = skipped
    report.error_count = errors
    report.save()

    return Response({
        'action': 'import',
        'success': True,
        'report': ImportReportSerializer(report).data,
        'summary': {
            'total_rows': result['summary']['total_rows'],
            'imported': imported,
            'skipped': skipped,
            'errors': errors,
            'anomalies': result['summary']['total_anomalies'],
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def import_reports(request, group_id):
    """List import reports for a group."""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    reports = group.import_reports.prefetch_related('anomalies').all()
    serializer = ImportReportSerializer(reports, many=True)
    return Response(serializer.data)


@api_view(['PUT'])
def review_anomaly(request, group_id, report_id, anomaly_id):
    """
    Approve or reject a specific import anomaly.

    This endpoint satisfies Meera's requirement:
    "Clean up the duplicates — but I want to approve anything the app deletes or changes."

    Accepts:
        status: 'user_approved' | 'user_rejected'
        notes: optional user notes about the decision
    """
    try:
        anomaly = ImportAnomaly.objects.get(
            id=anomaly_id,
            import_report_id=report_id,
            import_report__group_id=group_id,
        )
    except ImportAnomaly.DoesNotExist:
        return Response({'error': 'Anomaly not found'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    if new_status not in ('user_approved', 'user_rejected'):
        return Response(
            {'error': 'status must be "user_approved" or "user_rejected"'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    anomaly.status = new_status
    if 'notes' in request.data:
        anomaly.description += f' | User note: {request.data["notes"]}'
    anomaly.save()

    return Response({
        'id': anomaly.id,
        'row_number': anomaly.row_number,
        'category': anomaly.category,
        'status': anomaly.status,
        'description': anomaly.description,
    })

