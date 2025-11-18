from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch
from django.test import TestCase
from tickets.models import Event, Booking
from tickets.reconciliation import ReconciliationService


class ReconciliationServiceTests(TestCase):
    """Tests for the ReconciliationService."""

    def setUp(self):
        """Create test fixtures."""
        self.event = Event.objects.create(
            slug="test-event",
            name="Test Event",
            venue_details="Test Venue",
            ticket_price=Decimal("10.00"),
            reference_prefix="TST",
            bank_account_name="Test Account",
            sort_code="12-34-56",
            account_number="12345678",
            contact_email="test@example.com",
            admin_notification_emails="admin@example.com",
        )

        # Create some unpaid bookings
        self.booking1 = Booking.objects.create(
            event=self.event,
            full_name="John Smith",
            email="john@example.com",
            num_tickets=1,
            donation_amount=Decimal("10.00"),
            is_paid=False,
        )

        self.booking2 = Booking.objects.create(
            event=self.event,
            full_name="Jane Doe",
            email="jane@example.com",
            num_tickets=2,
            donation_amount=Decimal("25.50"),
            is_paid=False,
        )

        self.booking3 = Booking.objects.create(
            event=self.event,
            full_name="Bob Wilson",
            email="bob@example.com",
            num_tickets=1,
            donation_amount=Decimal("10.00"),  # Same amount as booking1
            is_paid=False,
        )

        self.service = ReconciliationService(self.event)

    @patch('tickets.reconciliation.completion')
    def test_parse_csv_with_llm(self, mock_completion):
        """Test CSV parsing with LLM."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''[
            {"date": "2025-01-15", "amount": 10.00, "description": "Transfer from John Smith", "reference": "TST-1"},
            {"date": "2025-01-16", "amount": 25.50, "description": "Payment received", "reference": ""}
        ]'''
        mock_completion.return_value = mock_response

        # Create a mock CSV file
        csv_content = b"Date,Amount,Description\n2025-01-15,10.00,Transfer from John Smith\n"
        csv_file = BytesIO(csv_content)

        # Parse
        transactions = self.service.parse_csv_with_llm(csv_file)

        # Assertions
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0]['date'], '2025-01-15')
        self.assertEqual(transactions[0]['amount'], Decimal('10.00'))
        self.assertEqual(transactions[0]['description'], 'Transfer from John Smith')

    def test_match_transaction_exact_match(self):
        """Test exact match with reference and amount."""
        transaction = {
            'date': '2025-01-15',
            'amount': Decimal('10.00'),
            'description': 'Payment for TST-1',
            'reference': f'TST-{self.booking1.id}',
        }

        match = self.service.match_transaction(transaction)

        self.assertIsNotNone(match)
        self.assertEqual(match['booking'].id, self.booking1.id)
        self.assertEqual(match['confidence'], 'high')

    def test_match_transaction_single_amount_match(self):
        """Test matching with unique amount (no reference)."""
        transaction = {
            'date': '2025-01-16',
            'amount': Decimal('25.50'),
            'description': 'Payment received',
            'reference': '',
        }

        match = self.service.match_transaction(transaction)

        self.assertIsNotNone(match)
        self.assertEqual(match['booking'].id, self.booking2.id)
        self.assertEqual(match['confidence'], 'medium')

    def test_match_transaction_multiple_candidates(self):
        """Test when multiple bookings have the same amount."""
        transaction = {
            'date': '2025-01-17',
            'amount': Decimal('10.00'),
            'description': 'Payment',
            'reference': '',
        }

        match = self.service.match_transaction(transaction)

        self.assertIsNotNone(match)
        self.assertIsNone(match.get('booking'))
        self.assertIsNotNone(match.get('candidates'))
        self.assertEqual(len(match['candidates']), 2)  # booking1 and booking3
        self.assertEqual(match['confidence'], 'low')

    def test_match_transaction_no_match(self):
        """Test when transaction doesn't match any booking."""
        transaction = {
            'date': '2025-01-18',
            'amount': Decimal('99.99'),
            'description': 'Random payment',
            'reference': '',
        }

        match = self.service.match_transaction(transaction)

        self.assertIsNone(match)

    @patch('tickets.reconciliation.completion')
    def test_llm_suggest_match(self, mock_completion):
        """Test LLM suggestion for ambiguous matches."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"booking_number": 1, "confidence": "high", "reason": "Name matches description"}'''
        mock_completion.return_value = mock_response

        transaction = {
            'date': '2025-01-17',
            'amount': Decimal('10.00'),
            'description': 'Payment from John Smith',
            'reference': '',
        }

        candidates = [self.booking1, self.booking3]
        match = self.service.llm_suggest_match(transaction, candidates)

        self.assertIsNotNone(match)
        self.assertEqual(match['booking'].id, self.booking1.id)
        self.assertEqual(match['confidence'], 'high')

    @patch('tickets.reconciliation.completion')
    def test_reconcile_workflow(self, mock_completion):
        """Test the full reconciliation workflow."""
        # Mock LLM responses
        parse_response = Mock()
        parse_response.choices = [Mock()]
        parse_response.choices[0].message.content = '''[
            {"date": "2025-01-15", "amount": 10.00, "description": "Transfer TST-1", "reference": "TST-1"},
            {"date": "2025-01-16", "amount": 25.50, "description": "Payment", "reference": ""}
        ]'''

        mock_completion.return_value = parse_response

        # Create CSV
        csv_content = b"Date,Amount,Description\n2025-01-15,10.00,Transfer\n"
        csv_file = BytesIO(csv_content)

        # Run reconciliation
        results = self.service.reconcile(csv_file)

        # Assertions
        self.assertEqual(len(results), 2)
        self.assertIsNotNone(results[0]['match'])
        self.assertEqual(results[0]['match']['booking'].id, self.booking1.id)
        self.assertEqual(results[1]['match']['booking'].id, self.booking2.id)
