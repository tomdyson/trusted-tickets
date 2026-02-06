# Trusted Tickets

A Django-based multi-event ticket booking system with trust-based payments. Event organizers trust attendees to complete bank transfers after booking, eliminating payment processing fees and simplifying the booking flow.

## Key Features

- **Multi-Event Support**: Host multiple events from a single instance, each with its own URL slug
- **Trust-Based Payments**: No online payment processing - attendees receive bank transfer details after booking
- **Quick Pay Links**: Optional integration with Monzo.me, PayPal.me, or other payment services for one-click payments
- **Flexible Pricing**: Support for fixed ticket prices, donations, or hybrid models
- **Gift Aid Support**: Built-in UK Gift Aid handling for charitable donations with CSV export for tax purposes
- **Customizable Emails**: Per-event email templates with Django template syntax
- **Admin Dashboard**: Comprehensive booking management and reporting
- **Zero Payment Fees**: No Stripe/PayPal fees - just direct bank transfers
- **Docker Ready**: Optimized for deployment on Coolify, Fly.io, or any Docker platform
- **Fast Dependencies**: Uses `uv` for lightning-fast dependency installation

## Quick Start

### Requirements

- Python 3.12 or higher
- PostgreSQL (optional, SQLite works for development)

### Local Development

1. **Clone and setup**:
   ```bash
   git clone https://github.com/tomdyson/trusted-tickets.git
   cd trusted-tickets
   ```

2. **Install dependencies with uv**:
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Run migrations and create superuser**:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Start development server**:
   ```bash
   python manage.py runserver
   ```

5. **Access the admin** at `http://localhost:8000/admin` and create your first event!

### Docker Development

```bash
docker-compose up
# Access at http://localhost:8000
```

## Deployment to Coolify

Coolify makes deployment straightforward with its Docker support.

### Step 1: Prepare Your Repository

1. Push your code to GitHub
2. Ensure `.dockerignore` and `Dockerfile` are present (they are!)

### Step 2: Create New Resource in Coolify

1. Log into your Coolify dashboard
2. Click **+ New Resource** → **Application**
3. Select **Public Repository** and enter your GitHub URL
4. Choose your server and click **Continue**

### Step 3: Configure Build Settings

1. **Build Pack**: Docker
2. **Dockerfile Location**: `./Dockerfile` (default)
3. **Port**: 8000 (Coolify will set the PORT env var)

### Step 4: Environment Variables

Add these environment variables in Coolify:

```bash
# Required
SECRET_KEY=your-secret-key-generate-with-openssl-rand-base64-32
DATABASE_URL=postgresql://user:password@host:5432/dbname
EMAIL_HOST_PASSWORD=your-resend-api-key

# Recommended
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
DEFAULT_FROM_EMAIL=Event Tickets <noreply@yourdomain.com>
```

### Step 5: Add PostgreSQL Database

1. In Coolify, go to your project
2. Add **New Resource** → **Database** → **PostgreSQL**
3. Copy the DATABASE_URL and add it to your app's environment variables

### Step 6: Deploy

**Option A: Via Coolify Dashboard**
1. Click **Deploy** in Coolify
2. Wait for build to complete (uv makes this fast!)
3. Access your app at your configured domain

**Option B: Via Coolify CLI**
Once changes have been pushed to main, you can deploy directly from the command line:
```bash
coolify deploy name trusted-tickets
```

### Step 7: Create Admin User

After first deployment, run in Coolify's terminal:

```bash
python manage.py createsuperuser
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | Django secret key (use `openssl rand -base64 32`) |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `DEBUG` | No | `False` | Enable debug mode (never in production!) |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated list of allowed hosts (note: codebase may have custom defaults) |
| `CSRF_TRUSTED_ORIGINS` | No | `http://localhost` | Comma-separated list of trusted origins (include `https://` for production) |
| `EMAIL_HOST_PASSWORD` | Yes* | - | Resend API key for sending emails |
| `DEFAULT_FROM_EMAIL` | No | `Trusted Tickets <noreply@example.com>` | From address for emails |
| `PORT` | No | `8000` | Port for Gunicorn (Coolify sets this automatically) |

\* Required for email functionality

### Email Setup (Resend)

1. Sign up at [resend.com](https://resend.com) (free tier: 100 emails/day)
2. Verify your sending domain
3. Create an API key
4. Add to `EMAIL_HOST_PASSWORD` environment variable

**Note**: You only need one Resend account/API key. The `DEFAULT_FROM_EMAIL` will be the sender for all events, but each event can have its own Reply-To address via the `contact_email` field. When customers reply to confirmation emails, replies go to the event-specific contact email.

## Creating Your First Event

1. **Access Admin**: Go to `https://yourdomain.com/admin`

2. **Create Event**:
   - Click **Events** → **Add Event**
   - Fill in the required fields:
     - **Slug**: URL identifier (e.g., `summer-concert` → `/summer-concert/`)
     - **Name**: Display name (e.g., "Summer Concert 2025")
     - **Venue Details**: Location, date, time (supports `<b>` and `<strong>` tags for emphasis)
   - **Form Options**:
     - **Collect Phone Number**: Enable to show phone number field on booking form (optional)

3. **Configure Pricing**:
   - **Ticket Price**: Set to £0 for donation-only events
   - **Is Donation Based**: Enable for Gift Aid support
   - **Allow Extra Donation**: Let attendees add extra donation

4. **Bank Details**:
   - Enter your bank account details for payment instructions
   - Set **Reference Prefix** (e.g., "SUM" → bookings like "SUM-123")
   - **Quick Pay Link** (optional): Add a quick payment link template for services like Monzo.me or PayPal.me
     - Use `{amount}` placeholder for the payment amount (e.g., `25.50`)
     - Use `{reference}` placeholder for the payment reference
     - Example: `https://monzo.me/username/{amount}?d={reference}` or `https://paypal.me/username/{amount}/GBP`
     - If set, a "Pay Now" button will appear on the booking confirmation page

5. **Email Configuration**:
   - **Contact Email**: Support email shown to customers (also used as Reply-To for confirmation emails)
   - **Admin Notification Emails**: Comma-separated list for booking notifications
   - **Confirmation Email**: Customize subject and body (see Email Templates below)

   **Reply-To Behavior**:
   - Customer confirmation emails use the event's `contact_email` as Reply-To (customers reply to event organizers)
   - Admin notification emails use the customer's email as Reply-To (admins can quickly reply to customers)

6. **Save** and your event is live at `https://yourdomain.com/your-slug/`!

## Email Templates

Email templates use Django template syntax with these available variables:

### Available Variables

- `{{ booking.full_name }}` - Customer's name
- `{{ booking.email }}` - Customer's email
- `{{ booking.num_tickets }}` - Number of tickets
- `{{ booking.donation_amount }}` - Total amount
- `{{ booking.gift_aid }}` - True/False gift aid status
- `{{ booking.booking_reference }}` - Reference code (e.g., "SUM-123")
- `{{ event.name }}` - Event name
- `{{ event.venue_details }}` - Venue information
- `{{ payment_reference }}` - Payment reference (same as booking reference)
- `{{ bank_account_name }}` - Bank account name
- `{{ sort_code }}` - Bank sort code
- `{{ account_number }}` - Bank account number

### Example Email Template

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .booking-details { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        .payment-info { background: #fff3cd; padding: 15px; margin-top: 15px; }
    </style>
</head>
<body>
    <h1>Booking Confirmation - {{ event.name }}</h1>

    <p>Dear {{ booking.full_name }},</p>

    <p>Thank you for booking {{ booking.num_tickets }} ticket(s) for {{ event.name }}.</p>

    <div class="booking-details">
        <h2>Your Booking</h2>
        <p><strong>Reference:</strong> {{ booking.booking_reference }}</p>
        <p><strong>Tickets:</strong> {{ booking.num_tickets }}</p>
        <p><strong>Total:</strong> £{{ booking.donation_amount }}</p>
        {% if booking.gift_aid %}
        <p><strong>Gift Aid:</strong> Yes - Thank you!</p>
        {% endif %}
    </div>

    <div class="payment-info">
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
    </div>

    <p>Looking forward to seeing you at {{ event.venue_details }}!</p>

    <p>Best regards,<br>The Team</p>
</body>
</html>
```

## Admin Features

### Booking Management

- View all bookings with filtering (payment status, gift aid, search)
- Mark bookings as paid/unpaid
- Export data (via Django admin)
- Email customers directly from admin

### Event Management

- Create/edit/duplicate events
- View booking counts and revenue per event
- Quick links to event reports
- Clone events for easy setup of similar events

### Reports

Access per-event reports at: `https://yourdomain.com/event-slug/report/`

Features:
- Summary statistics (bookings, tickets, revenue)
- Payment status breakdown
- Gift aid tracking
- Search and filter bookings
- Pagination for large events
- One-click "Copy emails" for unique BCC list (Name <email> format)

### Gift Aid Export

For donation-based events, export Gift Aid data as CSV for tax purposes:
- Access at: `https://yourdomain.com/event-slug/gift-aid-export/`
- Only available for events with `is_donation_based` enabled
- Requires staff login
- Exports: Name, Email, Donation Amount, Date, and full address for all Gift Aid bookings
- CSV filename format: `{event-slug}-gift-aid-{timestamp}.csv`

### Export Email Addresses

To get a comma-separated list of all unique email addresses for an event:

```bash
psql "YOUR_DATABASE_URL" -c "SELECT string_agg(DISTINCT email, ', ') as emails FROM tickets_booking b JOIN tickets_event e ON b.event_id = e.id WHERE e.slug = 'your-event-slug';"
```

Replace `YOUR_DATABASE_URL` with your PostgreSQL connection string and `your-event-slug` with the event's slug.

## Development

### Project Structure

```
trusted-tickets/
├── Dockerfile              # Docker build configuration
├── docker-compose.yml      # Local development setup
├── pyproject.toml          # Dependencies (managed by uv)
├── manage.py               # Django management script
├── trusted_tickets/        # Django project
│   ├── settings.py         # Configuration
│   ├── urls.py             # Root URL routing
│   └── wsgi.py             # WSGI application
└── tickets/                # Main app
    ├── models.py           # Event & Booking models
    ├── views.py            # Booking views
    ├── forms.py            # Form handling
    ├── admin.py            # Admin customization
    ├── urls.py             # App routing
    ├── utils.py            # Email utilities
    └── templates/          # HTML templates
```

### Adding Dependencies

```bash
# Add a new package
uv pip install package-name

# Update pyproject.toml manually or use:
# (uv doesn't auto-update pyproject.toml from CLI yet)
```

### Running Tests

```bash
python manage.py test
```

### Database Migrations

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## Security Considerations

- Always use strong `SECRET_KEY` in production
- Set `DEBUG=False` in production
- Use HTTPS (Coolify provides this automatically)
- Restrict `ALLOWED_HOSTS` to your domain only
- Keep `EMAIL_HOST_PASSWORD` secret
- Regularly update dependencies: `uv pip install --upgrade -e .`

## Troubleshooting

### Emails not sending

- Check `EMAIL_HOST_PASSWORD` is set
- Verify Resend domain is verified
- Check Django logs for errors

### Static files not loading

- Ensure `python manage.py collectstatic` ran during build
- Check WhiteNoise middleware is enabled (it is by default)

### Database connection errors

- Verify `DATABASE_URL` format: `postgresql://user:pass@host:5432/dbname`
- Ensure PostgreSQL is running and accessible

### "DisallowedHost" error

- Add your domain to `ALLOWED_HOSTS` environment variable
- Add your domain with `https://` to `CSRF_TRUSTED_ORIGINS`

## License

MIT License - feel free to use for your events!

## Support

- **Issues**: [GitHub Issues](https://github.com/tomdyson/trusted-tickets/issues)
- **Discussions**: [GitHub Discussions](https://github.com/tomdyson/trusted-tickets/discussions)

## Credits

Built with:
- [Django 5.2](https://www.djangoproject.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Alpine.js](https://alpinejs.dev/)
- [uv](https://github.com/astral-sh/uv) for fast dependency management
- [Resend](https://resend.com/) for email delivery

Inspired by the need for simple, fee-free event ticketing where trust matters more than automation.
