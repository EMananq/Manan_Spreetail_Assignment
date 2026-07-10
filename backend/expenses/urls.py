"""
URL routing for the expenses app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/me/', views.me, name='me'),

    # Groups
    path('groups/', views.groups_list, name='groups-list'),
    path('groups/<int:group_id>/', views.group_detail, name='group-detail'),

    # Group Members
    path('groups/<int:group_id>/members/', views.group_members, name='group-members'),
    path('groups/<int:group_id>/members/<int:membership_id>/', views.update_membership, name='update-membership'),

    # Expenses
    path('groups/<int:group_id>/expenses/', views.group_expenses, name='group-expenses'),

    # Settlements
    path('groups/<int:group_id>/settlements/', views.group_settlements, name='group-settlements'),

    # Balances
    path('groups/<int:group_id>/balances/', views.group_balances, name='group-balances'),

    # Import
    path('groups/<int:group_id>/import/', views.import_csv, name='import-csv'),
    path('groups/<int:group_id>/import-reports/', views.import_reports, name='import-reports'),

    # Anomaly Approval (Meera's requirement)
    path('groups/<int:group_id>/import-reports/<int:report_id>/anomalies/<int:anomaly_id>/',
         views.review_anomaly, name='review-anomaly'),
]
