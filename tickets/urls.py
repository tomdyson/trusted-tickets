from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path

from .views import (
    BookingConfirmationView,
    BookingCreateView,
    BookingReportView,
    GiftAidExportView,
)

urlpatterns = [
    # Event-specific booking pages
    path(
        "<slug:event_slug>/",
        BookingCreateView.as_view(),
        name="event_booking"
    ),
    path(
        "<slug:event_slug>/confirmation/<int:pk>/",
        BookingConfirmationView.as_view(),
        name="booking_confirmation",
    ),
    path(
        "<slug:event_slug>/report/",
        staff_member_required(BookingReportView.as_view()),
        name="booking_report",
    ),
    path(
        "<slug:event_slug>/gift-aid-export/",
        staff_member_required(GiftAidExportView.as_view()),
        name="gift_aid_export",
    ),
]
