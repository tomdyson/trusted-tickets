from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView

from .forms import BookingForm, ReportFilterForm
from .models import Booking, Event
from .utils import send_admin_notification_email, send_booking_confirmation_email


class BookingCreateView(CreateView):
    """Event-aware booking creation view."""
    model = Booking
    form_class = BookingForm
    template_name = "tickets/booking_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Get the event from the URL slug
        self.event = get_object_or_404(Event, slug=self.kwargs['event_slug'], is_active=True)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.event
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.event
        return context

    def form_valid(self, form):
        # Check for duplicate submissions (same email within last 60 seconds)
        email = form.cleaned_data.get("email")
        num_tickets = form.cleaned_data.get("num_tickets")
        extra_donation = form.cleaned_data.get("extra_donation", 0) or 0
        donation_amount = num_tickets * self.event.ticket_price + extra_donation

        # Look for recent bookings with same email, tickets, and donation amount
        cutoff_time = timezone.now() - timedelta(seconds=60)
        recent_duplicate = Booking.objects.filter(
            event=self.event,
            email=email,
            num_tickets=num_tickets,
            donation_amount=donation_amount,
            created_at__gte=cutoff_time,
        ).first()

        if recent_duplicate:
            # Redirect to the existing booking's confirmation page
            messages.info(
                self.request,
                "This booking was already submitted. Showing your confirmation details.",
            )
            return redirect("booking_confirmation", event_slug=self.event.slug, pk=recent_duplicate.id)

        # Save the booking to the database
        self.object = form.save()

        # Send confirmation email to the customer
        email_sent = send_booking_confirmation_email(self.request, self.object)
        if email_sent:
            messages.success(
                self.request,
                "Your booking was successful! A confirmation email has been sent.",
            )
        else:
            messages.warning(
                self.request,
                "Your booking was successful, but there was an issue sending the confirmation email.",
            )

        # Send notification email to admins
        send_admin_notification_email(self.request, self.object)

        # Redirect to the confirmation page with the booking ID
        return redirect("booking_confirmation", event_slug=self.event.slug, pk=self.object.id)


class BookingConfirmationView(TemplateView):
    """Display booking confirmation details."""
    template_name = "tickets/booking_confirmation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_slug = self.kwargs.get("event_slug")
        booking_id = self.kwargs.get("pk")

        try:
            event = Event.objects.get(slug=event_slug)
            booking = Booking.objects.get(id=booking_id, event=event)
            context["event"] = event
            context["booking"] = booking
            context["payment_reference"] = booking.payment_reference()
            # Use bank details from event
            context["bank_details"] = {
                "account_name": event.bank_account_name,
                "sort_code": event.sort_code,
                "account_number": event.account_number,
                "reference": booking.payment_reference(),
            }
        except (Event.DoesNotExist, Booking.DoesNotExist):
            messages.error(self.request, "Booking not found.")
            context["error"] = "Booking information not found."

        return context


class BookingReportView(ListView):
    """Staff-only booking report for a specific event."""
    model = Booking
    template_name = "tickets/booking_report.html"
    context_object_name = "bookings"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Get the event from the URL slug
        self.event = get_object_or_404(Event, slug=self.kwargs['event_slug'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Booking.objects.filter(event=self.event).order_by("-created_at")

        # Apply filters from form
        form = ReportFilterForm(self.request.GET)
        if form.is_valid():
            # Filter by payment status
            payment_status = form.cleaned_data.get("payment_status")
            if payment_status == "paid":
                queryset = queryset.filter(is_paid=True)
            elif payment_status == "unpaid":
                queryset = queryset.filter(is_paid=False)

            # Filter by gift aid status
            gift_aid = form.cleaned_data.get("gift_aid")
            if gift_aid == "yes":
                queryset = queryset.filter(gift_aid=True)
            elif gift_aid == "no":
                queryset = queryset.filter(gift_aid=False)

            # Search by name or email
            search_query = form.cleaned_data.get("search")
            if search_query:
                queryset = queryset.filter(
                    Q(full_name__icontains=search_query)
                    | Q(email__icontains=search_query)
                )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.event

        # Add filter form to context
        form = ReportFilterForm(self.request.GET or None)
        context["filter_form"] = form

        # Add summary statistics
        bookings = self.get_queryset()
        context["total_bookings"] = bookings.count()
        context["total_tickets"] = (
            bookings.aggregate(Sum("num_tickets"))["num_tickets__sum"] or 0
        )
        context["total_amount"] = (
            bookings.aggregate(Sum("donation_amount"))["donation_amount__sum"] or 0
        )
        context["paid_amount"] = (
            bookings.filter(is_paid=True).aggregate(Sum("donation_amount"))[
                "donation_amount__sum"
            ]
            or 0
        )
        context["unpaid_amount"] = (
            bookings.filter(is_paid=False).aggregate(Sum("donation_amount"))[
                "donation_amount__sum"
            ]
            or 0
        )
        context["gift_aid_count"] = bookings.filter(gift_aid=True).count()

        # Make booking references available for all bookings in the template
        for booking in context["bookings"]:
            booking.ref = booking.booking_reference()

        return context
