import csv
from datetime import timedelta

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView

from .forms import BookingForm, ReportFilterForm
from .models import Booking, Event
from .utils import (
    generate_quick_pay_url,
    send_admin_notification_email,
    send_booking_confirmation_email,
)


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
            # Generate quick pay URL if event has quick_pay_link set
            context["quick_pay_url"] = generate_quick_pay_url(event, booking.donation_amount, booking.payment_reference())
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

        all_bookings = (
            Booking.objects.filter(event=self.event)
            .order_by("created_at")
            .values_list("email", "full_name")
        )
        seen_emails = set()
        bcc_entries = []
        for email, full_name in all_bookings:
            if not email:
                continue
            normalized_email = email.strip().lower()
            if normalized_email in seen_emails:
                continue
            seen_emails.add(normalized_email)
            name = (full_name or "").strip()
            if name:
                bcc_entries.append(f"{name} <{email.strip()}>")
            else:
                bcc_entries.append(email.strip())
        context["bcc_emails"] = ", ".join(bcc_entries)
        context["bcc_emails_count"] = len(bcc_entries)

        # Make booking references available for all bookings in the template
        for booking in context["bookings"]:
            booking.ref = booking.booking_reference()

        return context


class GiftAidExportView(View):
    def get(self, request, event_slug):
        event = get_object_or_404(Event, slug=event_slug)
        if not event.is_donation_based:
            raise Http404("Gift Aid export not available for this event.")

        bookings = event.bookings.filter(gift_aid=True).order_by("created_at")

        response = HttpResponse(content_type="text/csv")
        timestamp = timezone.now().strftime("%Y%m%d")
        filename = f"{event.slug}-gift-aid-{timestamp}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            "Full Name",
            "Email",
            "Donation Amount",
            "Donation Date",
            "Address Line 1",
            "Address Line 2",
            "City",
            "Postcode",
        ])

        current_tz = timezone.get_current_timezone()
        for booking in bookings:
            donation_date = booking.created_at.astimezone(current_tz).strftime("%Y-%m-%d")
            writer.writerow([
                booking.full_name,
                booking.email,
                f"{booking.donation_amount}",
                donation_date,
                booking.address_line1 or "",
                booking.address_line2 or "",
                booking.city or "",
                booking.postcode or "",
            ])

        return response


class ReconciliationView(TemplateView):
    """Bank statement reconciliation view."""
    template_name = "tickets/reconciliation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_slug = self.kwargs.get("event_slug")
        context["event"] = get_object_or_404(Event, slug=event_slug)
        
        # Get reconciliation results from session if available
        results = self.request.session.get(f"reconciliation_results_{event_slug}")
        if results:
            context["results"] = results
            
        return context

    def post(self, request, *args, **kwargs):
        event_slug = self.kwargs.get("event_slug")
        event = get_object_or_404(Event, slug=event_slug)
        
        # Handle file upload
        if "csv_file" in request.FILES:
            csv_file = request.FILES["csv_file"]
            
            # Get LLM configuration from request or use defaults
            llm_provider = request.POST.get("llm_provider", "openai")
            llm_model = request.POST.get("llm_model", "gpt-4o-mini")
            
            try:
                from .reconciliation import ReconciliationService
                
                service = ReconciliationService(event, llm_provider, llm_model)
                results = service.reconcile(csv_file)
                
                # Store results in session for display
                # Serialize for session storage
                serialized_results = []
                for result in results:
                    match = result.get("match")
                    serialized_match = None
                    
                    if match:
                        serialized_match = {
                            "confidence": match.get("confidence"),
                            "reason": match.get("reason"),
                        }
                        
                        if match.get("booking"):
                            booking = match["booking"]
                            serialized_match["booking"] = {
                                "id": booking.id,
                                "reference": booking.payment_reference(),
                                "name": booking.full_name,
                                "email": booking.email,
                                "amount": str(booking.donation_amount),
                                "num_tickets": booking.num_tickets,
                            }
                        elif match.get("candidates"):
                            serialized_match["candidates"] = [
                                {
                                    "id": b.id,
                                    "reference": b.payment_reference(),
                                    "name": b.full_name,
                                    "email": b.email,
                                    "amount": str(b.donation_amount),
                                    "num_tickets": b.num_tickets,
                                }
                                for b in match["candidates"]
                            ]
                    
                    serialized_results.append({
                        "transaction": {
                            "date": result["transaction"]["date"],
                            "amount": str(result["transaction"]["amount"]),
                            "description": result["transaction"]["description"],
                            "reference": result["transaction"].get("reference", ""),
                        },
                        "match": serialized_match,
                    })
                
                request.session[f"reconciliation_results_{event_slug}"] = serialized_results
                messages.success(request, f"Parsed {len(results)} transactions from CSV.")
                
            except Exception as e:
                messages.error(request, f"Error processing CSV: {str(e)}")
        
        # Handle confirmation of a match
        elif "confirm_match" in request.POST:
            booking_id = request.POST.get("booking_id")
            try:
                booking = Booking.objects.get(id=booking_id, event=event)
                booking.is_paid = True
                booking.save()
                messages.success(
                    request,
                    f"Marked {booking.payment_reference()} as paid."
                )
                
                # Remove this transaction from session results
                results = request.session.get(f"reconciliation_results_{event_slug}", [])
                transaction_index = int(request.POST.get("transaction_index", -1))
                if 0 <= transaction_index < len(results):
                    results.pop(transaction_index)
                    request.session[f"reconciliation_results_{event_slug}"] = results
                    
            except Booking.DoesNotExist:
                messages.error(request, "Booking not found.")
        
        return redirect("reconciliation", event_slug=event_slug)

