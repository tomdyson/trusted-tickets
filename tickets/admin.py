from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import Booking, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "ticket_price",
        "is_donation_based",
        "is_active",
        "booking_count",
        "total_revenue",
        "created_at",
    )
    list_filter = ("is_active", "is_donation_based", "created_at")
    search_fields = ("name", "slug", "venue_details")
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "slug", "venue_details", "is_active")},
        ),
        ("Form Options", {"fields": ("collect_phone_number",)}),
        (
            "Pricing & Options",
            {
                "fields": (
                    "ticket_price",
                    "is_donation_based",
                    "allow_extra_donation",
                    "reference_prefix",
                )
            },
        ),
        (
            "Bank Details",
            {
                "fields": (
                    "bank_account_name",
                    "sort_code",
                    "account_number",
                    "quick_pay_link",
                )
            },
        ),
        (
            "Email Configuration",
            {
                "fields": (
                    "contact_email",
                    "admin_notification_emails",
                    "confirmation_email_subject",
                    "confirmation_email_body",
                ),
                "description": "Available template variables: {{ booking.full_name }}, {{ booking.email }}, {{ booking.num_tickets }}, {{ booking.donation_amount }}, {{ booking.gift_aid }}, {{ booking.booking_reference }}, {{ event.name }}, {{ event.venue_details }}, {{ payment_reference }}, {{ bank_account_name }}, {{ sort_code }}, {{ account_number }}",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ("created_at", "updated_at")

    def booking_count(self, obj):
        """Display number of bookings for this event."""
        count = obj.bookings.count()
        return format_html(
            '<a href="/admin/tickets/booking/?event__id__exact={}">{}</a>',
            obj.id,
            count,
        )

    booking_count.short_description = "Bookings"

    def total_revenue(self, obj):
        """Display total revenue for this event."""
        total = (
            obj.bookings.aggregate(Sum("donation_amount"))["donation_amount__sum"] or 0
        )
        return f"£{total:.2f}"

    total_revenue.short_description = "Total Revenue"

    actions = ["duplicate_event"]

    def duplicate_event(self, request, queryset):
        """Action to duplicate selected events."""
        for event in queryset:
            event.pk = None
            event.slug = f"{event.slug}-copy"
            event.is_active = False
            event.save()
        self.message_user(
            request, f"{queryset.count()} event(s) duplicated successfully."
        )

    duplicate_event.short_description = "Duplicate selected events"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference_display",
        "event",
        "full_name",
        "email",
        "num_tickets",
        "donation_amount",
        "gift_aid",
        "is_paid",
        "created_at",
    )
    list_filter = ("event", "is_paid", "gift_aid", "created_at")
    search_fields = ("full_name", "email", "id")
    readonly_fields = (
        "booking_reference_display",
        "payment_reference_display",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Event", {"fields": ("event",)}),
        (
            "Booking Information",
            {
                "fields": (
                    "booking_reference_display",
                    "full_name",
                    "email",
                    "phone_number",
                    "num_tickets",
                    "donation_amount",
                )
            },
        ),
        ("Payment Status", {"fields": ("is_paid", "payment_reference_display")}),
        (
            "Gift Aid Information",
            {
                "fields": (
                    "gift_aid",
                    "address_line1",
                    "address_line2",
                    "city",
                    "postcode",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def booking_reference_display(self, obj):
        """Display booking reference."""
        if obj.id:
            return obj.booking_reference()
        return "-"

    booking_reference_display.short_description = "Booking Reference"

    def payment_reference_display(self, obj):
        """Display payment reference."""
        if obj.id:
            return obj.payment_reference()
        return "-"

    payment_reference_display.short_description = "Payment Reference"

    actions = ["mark_as_paid", "mark_as_unpaid"]

    def mark_as_paid(self, request, queryset):
        """Mark selected bookings as paid."""
        updated = queryset.update(is_paid=True)
        self.message_user(request, f"{updated} booking(s) marked as paid.")

    mark_as_paid.short_description = "Mark selected bookings as paid"

    def mark_as_unpaid(self, request, queryset):
        """Mark selected bookings as unpaid."""
        updated = queryset.update(is_paid=False)
        self.message_user(request, f"{updated} booking(s) marked as unpaid.")

    mark_as_unpaid.short_description = "Mark selected bookings as unpaid"
