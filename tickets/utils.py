from django.core.mail import send_mail
from django.template import Template, Context
from django.utils.html import strip_tags
from django.conf import settings


def render_email_template(template_string, context_dict):
    """
    Render a Django template string with the given context.

    Args:
        template_string: String containing Django template syntax
        context_dict: Dictionary of variables to use in template

    Returns:
        Rendered template string
    """
    template = Template(template_string)
    context = Context(context_dict)
    return template.render(context)


def send_booking_confirmation_email(request, booking):
    """
    Send a booking confirmation email to the customer using the event's template.

    Args:
        request: The HTTP request object
        booking: The Booking instance

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    event = booking.event

    # Prepare context for email template
    context = {
        'booking': booking,
        'event': event,
        'payment_reference': booking.payment_reference(),
        'bank_account_name': event.bank_account_name,
        'sort_code': event.sort_code,
        'account_number': event.account_number,
    }

    # Render subject and body with event's template
    try:
        subject = render_email_template(event.confirmation_email_subject, context)
        html_message = render_email_template(event.confirmation_email_body, context)
    except Exception as e:
        print(f"Error rendering email template: {str(e)}")
        return False

    # Create plain text version by stripping HTML tags
    plain_message = strip_tags(html_message)

    # Send email with Reply-To header
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.email],
            html_message=html_message,
            fail_silently=False,
            headers={'Reply-To': event.contact_email},
        )
        return True
    except Exception as e:
        # Log the error
        print(f"Error sending booking confirmation email: {str(e)}")
        return False


def send_admin_notification_email(request, booking):
    """
    Send a notification email to admins when a new booking is received.

    Args:
        request: The HTTP request object
        booking: The Booking instance

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    event = booking.event
    admin_emails = event.get_admin_emails()

    if not admin_emails:
        print("No admin emails configured for this event")
        return False

    subject = f'New Booking: {event.name} - {booking.full_name} - {booking.num_tickets} tickets'

    # Build admin URL
    if request:
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        admin_url = f"{protocol}://{domain}/admin/tickets/booking/{booking.id}/change/"
    else:
        admin_url = "#"

    # Simple text message for admin notification
    message = f"""
New booking received for {event.name}

Booking Details:
- Reference: {booking.booking_reference()}
- Name: {booking.full_name}
- Email: {booking.email}
- Phone: {booking.phone_number or 'N/A'}
- Tickets: {booking.num_tickets}
- Amount: £{booking.donation_amount}
- Gift Aid: {'Yes' if booking.gift_aid else 'No'}

Payment Reference: {booking.payment_reference()}

View in admin: {admin_url}
"""

    # Send email with Reply-To set to customer's email for easy replies
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
            headers={'Reply-To': booking.email},
        )
        return True
    except Exception as e:
        # Log the error
        print(f"Error sending admin notification email: {str(e)}")
        return False
