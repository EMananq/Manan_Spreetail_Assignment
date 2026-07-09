"""
Database seeder for FairSplit demo data.

Creates demo users (Aisha, Rohan, Priya, Meera, Dev, Sam, Kabir)
and the "Flat Expenses" group with temporal memberships.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fairsplit.settings')
django.setup()

from expenses.models import User, Group, GroupMembership


def seed():
    print("🌱 Seeding FairSplit database...")

    # Create demo users
    users_data = [
        {'email': 'aisha@flat.app', 'name': 'Aisha', 'password': 'password123'},
        {'email': 'rohan@flat.app', 'name': 'Rohan', 'password': 'password123'},
        {'email': 'priya@flat.app', 'name': 'Priya', 'password': 'password123'},
        {'email': 'meera@flat.app', 'name': 'Meera', 'password': 'password123'},
        {'email': 'dev@flat.app', 'name': 'Dev', 'password': 'password123'},
        {'email': 'sam@flat.app', 'name': 'Sam', 'password': 'password123'},
        {'email': 'kabir@flat.app', 'name': 'Kabir', 'password': 'password123'},
    ]

    users = {}
    for data in users_data:
        user, created = User.objects.get_or_create(
            email=data['email'],
            defaults={'name': data['name']},
        )
        if created:
            user.set_password(data['password'])
            user.save()
            print(f"  ✅ Created user: {data['name']} ({data['email']})")
        else:
            print(f"  ⏩ User exists: {data['name']} ({data['email']})")
        users[data['name']] = user

    # Create group
    group, created = Group.objects.get_or_create(
        name='Flat Expenses',
        defaults={'description': 'Shared flat expenses tracker', 'default_currency': 'INR'},
    )
    if created:
        print(f"  ✅ Created group: {group.name}")
    else:
        print(f"  ⏩ Group exists: {group.name}")

    # Memberships with temporal dates
    memberships_data = [
        {'user': 'Aisha',  'joined_at': '2026-01-01', 'left_at': None, 'role': 'admin'},
        {'user': 'Rohan',  'joined_at': '2026-01-01', 'left_at': None, 'role': 'member'},
        {'user': 'Priya',  'joined_at': '2026-01-01', 'left_at': None, 'role': 'member'},
        {'user': 'Meera',  'joined_at': '2026-01-01', 'left_at': '2026-03-31', 'role': 'member'},
        {'user': 'Dev',    'joined_at': '2026-01-01', 'left_at': None, 'role': 'member'},
        {'user': 'Sam',    'joined_at': '2026-04-08', 'left_at': None, 'role': 'member'},
        {'user': 'Kabir',  'joined_at': '2026-03-11', 'left_at': '2026-03-11', 'role': 'member'},
    ]

    for data in memberships_data:
        membership, created = GroupMembership.objects.get_or_create(
            group=group,
            user=users[data['user']],
            joined_at=data['joined_at'],
            defaults={
                'left_at': data['left_at'],
                'role': data['role'],
            },
        )
        status_text = "active" if not data['left_at'] else f"left {data['left_at']}"
        if created:
            print(f"  ✅ Added {data['user']} to group ({status_text})")
        else:
            print(f"  ⏩ Membership exists: {data['user']} ({status_text})")

    print("\n🎉 Seed complete!")
    print(f"   Users: {User.objects.count()}")
    print(f"   Groups: {Group.objects.count()}")
    print(f"   Memberships: {GroupMembership.objects.count()}")


if __name__ == '__main__':
    seed()
