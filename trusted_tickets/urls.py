"""
URL configuration for trusted_tickets project.
"""
from django.contrib import admin
from django.urls import path, include

# Customize admin site
admin.site.site_header = "Trusted Tickets Admin"
admin.site.site_title = "Trusted Tickets Admin Portal"
admin.site.index_title = "Welcome to Trusted Tickets Admin Portal"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tickets.urls')),
]
