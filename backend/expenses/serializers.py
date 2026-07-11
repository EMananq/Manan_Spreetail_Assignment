"""
DRF Serializers for all FairSplit models.
"""

from rest_framework import serializers
from .models import (
    User, Group, GroupMembership, Expense,
    ExpenseSplit, Settlement, ImportReport, ImportAnomaly,
)


# ─── User ───────────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name']


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=6, write_only=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# ─── Group Membership ──────────────────────────────────────────────────
class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'user_id', 'user_name', 'joined_at', 'left_at', 'role']


# ─── Group ──────────────────────────────────────────────────────────────
class GroupSerializer(serializers.ModelSerializer):
    memberships = GroupMembershipSerializer(many=True, read_only=True)
    expense_count = serializers.SerializerMethodField()
    settlement_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'default_currency',
            'created_at', 'memberships', 'expense_count', 'settlement_count', 'member_count',
        ]

    def get_expense_count(self, obj):
        return obj.expenses.count()

    def get_settlement_count(self, obj):
        return obj.settlements.count()

    def get_member_count(self, obj):
        return obj.memberships.count()


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    default_currency = serializers.CharField(max_length=3, default='INR')


# ─── Expense Split ─────────────────────────────────────────────────────
class ExpenseSplitSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ['id', 'user', 'user_id', 'amount', 'share_value', 'percentage']


# ─── Expense ────────────────────────────────────────────────────────────
class ExpenseSerializer(serializers.ModelSerializer):
    paid_by_user = UserMinimalSerializer(source='paid_by', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.name', read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'group', 'paid_by', 'paid_by_user', 'paid_by_name', 'description',
            'amount', 'currency', 'split_type', 'expense_date',
            'notes', 'status', 'import_row_number', 'created_at', 'splits',
        ]
        read_only_fields = ['id', 'created_at']


class ExpenseCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=500)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='INR')
    split_type = serializers.ChoiceField(choices=['equal', 'unequal', 'percentage', 'share'])
    expense_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)
    paid_by_id = serializers.IntegerField(required=False)
    split_with = serializers.ListField(child=serializers.IntegerField())
    split_details = serializers.DictField(required=False)


# ─── Settlement ─────────────────────────────────────────────────────────
class SettlementSerializer(serializers.ModelSerializer):
    from_user_data = UserMinimalSerializer(source='from_user', read_only=True)
    to_user_data = UserMinimalSerializer(source='to_user', read_only=True)
    from_user_name = serializers.CharField(source='from_user.name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.name', read_only=True)

    class Meta:
        model = Settlement
        fields = [
            'id', 'group', 'from_user', 'to_user',
            'from_user_data', 'to_user_data',
            'from_user_name', 'to_user_name',
            'amount', 'currency', 'settlement_date',
            'notes', 'import_row_number', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SettlementCreateSerializer(serializers.Serializer):
    from_user_id = serializers.IntegerField(required=False)
    to_user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='INR')
    settlement_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)


# ─── Import ─────────────────────────────────────────────────────────────
class ImportAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportAnomaly
        fields = [
            'id', 'row_number', 'severity', 'category',
            'description', 'original_value', 'corrected_value',
            'action_taken', 'status',
        ]


class ImportReportSerializer(serializers.ModelSerializer):
    anomalies = ImportAnomalySerializer(many=True, read_only=True)

    class Meta:
        model = ImportReport
        fields = [
            'id', 'group', 'filename', 'total_rows',
            'imported_count', 'skipped_count', 'error_count',
            'created_at', 'anomalies',
        ]
