"""
Database models for the FairSplit shared expenses app.

Models:
- User: Custom user model with email-based authentication
- Group: Expense sharing groups
- GroupMembership: Temporal memberships (joined_at / left_at)
- Expense: Individual expenses with split type
- ExpenseSplit: Per-user share of an expense
- Settlement: Direct payments between members
- ImportReport: CSV import audit trail
- ImportAnomaly: Individual anomaly records from imports
"""

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


# ─── Custom User Manager ───────────────────────────────────────────────
class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, name, password, **extra_fields)


# ─── User ───────────────────────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.name


# ─── Group ──────────────────────────────────────────────────────────────
class Group(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    default_currency = models.CharField(max_length=3, default='INR')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'groups'

    def __str__(self):
        return self.name


# ─── Group Membership (Temporal) ────────────────────────────────────────
class GroupMembership(models.Model):
    """
    Tracks when members join and leave groups.
    - joined_at: Date the member started participating
    - left_at: Date the member stopped (NULL = still active)
    This enables temporal checks like:
    - Sam joined April 8 → not charged for March expenses
    - Meera left March 31 → not charged for April expenses
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateField()
    left_at = models.DateField(blank=True, null=True)
    role = models.CharField(max_length=20, default='member')  # 'admin' or 'member'

    class Meta:
        db_table = 'group_memberships'
        unique_together = ('group', 'user', 'joined_at')

    def __str__(self):
        status = f"left {self.left_at}" if self.left_at else "active"
        return f"{self.user.name} in {self.group.name} ({status})"


# ─── Expense ────────────────────────────────────────────────────────────
class Expense(models.Model):
    SPLIT_TYPES = [
        ('equal', 'Equal'),
        ('unequal', 'Unequal'),
        ('percentage', 'Percentage'),
        ('share', 'Share'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('skipped', 'Skipped'),
        ('needs_review', 'Needs Review'),
        ('void', 'Void'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses_paid')
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    split_type = models.CharField(max_length=20, choices=SPLIT_TYPES)
    expense_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    import_row_number = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f"{self.description} ({self.currency} {self.amount})"


# ─── Expense Split ──────────────────────────────────────────────────────
class ExpenseSplit(models.Model):
    """
    Records how much each participant owes for an expense.
    The sum of all splits for an expense must equal the expense amount.
    """
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='splits')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_splits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    share_value = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    percentage = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'expense_splits'
        unique_together = ('expense', 'user')

    def __str__(self):
        return f"{self.user.name}: {self.amount}"


# ─── Settlement ─────────────────────────────────────────────────────────
class Settlement(models.Model):
    """
    Direct payment from one member to another.
    Separate from expenses — settlements don't have splits.
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_paid')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    settlement_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    import_row_number = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'settlements'
        ordering = ['-settlement_date', '-id']

    def __str__(self):
        return f"{self.from_user.name} → {self.to_user.name}: {self.currency} {self.amount}"


# ─── Import Report ──────────────────────────────────────────────────────
class ImportReport(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='import_reports')
    filename = models.CharField(max_length=500)
    total_rows = models.IntegerField()
    imported_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'import_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Import: {self.filename} ({self.imported_count}/{self.total_rows})"


# ─── Import Anomaly ─────────────────────────────────────────────────────
class ImportAnomaly(models.Model):
    SEVERITY_CHOICES = [
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    ACTION_CHOICES = [
        ('auto_corrected', 'Auto Corrected'),
        ('skipped', 'Skipped'),
        ('flagged', 'Flagged'),
        ('reclassified', 'Reclassified'),
        ('treated_as_refund', 'Treated as Refund'),
    ]
    STATUS_CHOICES = [
        ('auto_resolved', 'Auto Resolved'),
        ('needs_review', 'Needs Review'),
        ('user_approved', 'User Approved'),
        ('user_rejected', 'User Rejected'),
    ]

    import_report = models.ForeignKey(ImportReport, on_delete=models.CASCADE, related_name='anomalies')
    row_number = models.IntegerField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    category = models.CharField(max_length=50)
    description = models.TextField()
    original_value = models.TextField(blank=True, null=True)
    corrected_value = models.TextField(blank=True, null=True)
    action_taken = models.CharField(max_length=30, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='auto_resolved')

    class Meta:
        db_table = 'import_anomalies'
        ordering = ['row_number']

    def __str__(self):
        return f"Row #{self.row_number} [{self.severity}] {self.category}"
