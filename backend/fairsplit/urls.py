"""
Root URL configuration for the FairSplit project.
All API endpoints are under /api/ prefix.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('expenses.urls')),
]
