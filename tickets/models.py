from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify


class Event(models.Model):
    """Model representing a bookable event."""

    # Basic Information
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-safe identifier (e.g., 'cats-event' for /cats-event/)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Event name displayed on the booking page"
    )
    venue_details = models.TextField(
        help_text="Venue, date, time information"
    )

    # Form Configuration
    collect_phone_number = models.BooleanField(
        default=False,
        help_text="If true, shows phone number field on booking form"
    )

    # Pricing Configuration
    ticket_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Base price per ticket (£). Set to 0 for donation-only events."
    )
    is_donation_based = models.BooleanField(
        default=False,
        help_text="If true, shows Gift Aid option (for UK charitable donations)"
    )
    allow_extra_donation = models.BooleanField(
        default=False,
        help_text="Allow attendees to add an optional extra donation"
    )

    # Payment Details
    reference_prefix = models.CharField(
        max_length=10,
        default="TKT",
        help_text="Prefix for booking references (e.g., 'SIB' creates 'SIB-123')"
    )
    bank_account_name = models.CharField(max_length=255)
    sort_code = models.CharField(
        max_length=10,
        help_text="Format: 12-34-56"
    )
    account_number = models.CharField(
        max_length=20,
        help_text="Bank account number"
    )

    # Email Configuration
    contact_email = models.EmailField(
        help_text="Contact email shown to customers (also used as Reply-To address for confirmation emails)"
    )
    admin_notification_emails = models.TextField(
        help_text="Comma-separated list of emails to notify on new bookings"
    )
    confirmation_email_subject = models.CharField(
        max_length=255,
        default="Booking Confirmation - {{ event.name }}"
    )
    confirmation_email_body = models.TextField(
        help_text="HTML email template. Available variables: {{ booking.* }}, {{ event.* }}, {{ payment_reference }}, {{ bank_* }}",
        default="""<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<h1>Booking Confirmation</h1>
<p>Dear {{ booking.full_name }},</p>
<p>Thank you for booking {{ booking.num_tickets }} ticket(s) for {{ event.name }}.</p>

<h2>Your Booking</h2>
<p><strong>Reference:</strong> {{ booking.booking_reference }}<br>
<strong>Tickets:</strong> {{ booking.num_tickets }}<br>
<strong>Total:</strong> £{{ booking.donation_amount }}</p>

<h2>Payment Instructions</h2>
<p>Please complete payment via bank transfer:</p>
<ul>
<li><strong>Account Name:</strong> {{ bank_account_name }}</li>
<li><strong>Sort Code:</strong> {{ sort_code }}</li>
<li><strong>Account Number:</strong> {{ account_number }}</li>
<li><strong>Reference:</strong> {{ payment_reference }}</li>
<li><strong>Amount:</strong> £{{ booking.donation_amount }}</li>
</ul>
<p><strong>Important:</strong> Please include the reference number!</p>

<p>Looking forward to seeing you!<br>
Contact: {{ event.contact_email }}</p>
</body></html>"""
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Only active events accept new bookings"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not provided
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_admin_emails(self):
        """Return list of admin emails."""
        return [email.strip() for email in self.admin_notification_emails.split(',') if email.strip()]


class Booking(models.Model):
    """Model representing a ticket booking for an event."""

    # Event Reference
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    # Customer Information
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Booking Details
    num_tickets = models.PositiveIntegerField(default=1)
    donation_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount (tickets + optional donation)"
    )

    # Gift Aid Information
    gift_aid = models.BooleanField(default=False)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postcode = models.CharField(max_length=10, blank=True, null=True)

    # Payment Status
    is_paid = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"

    def __str__(self):
        return f"{self.booking_reference()} - {self.full_name}"

    def booking_reference(self):
        """Generate a booking reference from the event prefix and ID."""
        return f"{self.event.reference_prefix}-{self.id}"

    def payment_reference(self):
        """Generate a payment reference from the booking ID."""
        return self.booking_reference()

    def total_amount(self):
        """Calculate the total donation amount."""
        return self.donation_amount
