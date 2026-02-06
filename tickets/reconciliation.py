import csv
import io
import json
from decimal import Decimal
from typing import List, Dict, Optional, Any

from any_llm import completion
from django.conf import settings

from .models import Booking, Event


class ReconciliationService:
    """Service for reconciling bank statements with unpaid bookings."""

    def __init__(self, event: Event, llm_provider: str = "openai", llm_model: str = "gpt-4o-mini"):
        """
        Initialize the reconciliation service.

        Args:
            event: The event to reconcile bookings for
            llm_provider: LLM provider to use (e.g., 'openai', 'anthropic')
            llm_model: Model name to use
        """
        self.event = event
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    def parse_csv_with_llm(self, csv_file) -> List[Dict[str, Any]]:
        """
        Parse a bank statement CSV using LLM to handle varying formats.

        Args:
            csv_file: Uploaded CSV file

        Returns:
            List of standardized transaction dicts with keys:
            - date (str): Transaction date
            - amount (Decimal): Transaction amount
            - description (str): Transaction description
            - reference (str): Payment reference (if available)
        """
        # Read CSV content
        csv_content = csv_file.read().decode('utf-8')
        csv_file.seek(0)  # Reset file pointer

        # Prepare prompt for LLM
        prompt = f"""You are a bank statement parser. Parse the following CSV data into a standardized JSON format.

The CSV may have varying column names and formats from different banks. Extract the following fields:
- date: Transaction date (in YYYY-MM-DD format)
- amount: Transaction amount (as a number, positive for credits/incoming payments)
- description: Transaction description/narrative
- reference: Payment reference if present (look for codes like "TKT-123" or similar)

Only include INCOMING transactions (credits/deposits). Ignore debits/outgoing payments.

CSV Data:
{csv_content}

Return ONLY a valid JSON array of transaction objects. Each object should have: date, amount, description, and reference (use empty string if no reference found).

Example output format:
[
  {{"date": "2025-01-15", "amount": 25.50, "description": "Bank transfer from John Smith", "reference": "TKT-123"}},
  {{"date": "2025-01-16", "amount": 10.00, "description": "Payment received", "reference": ""}}
]
"""

        # Call LLM
        response = completion(
            model=self.llm_model,
            provider=self.llm_provider,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse LLM response
        llm_output = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if llm_output.startswith("```"):
            lines = llm_output.split("\n")
            llm_output = "\n".join(lines[1:-1])  # Remove first and last lines
        if llm_output.startswith("json"):
            llm_output = llm_output[4:].strip()

        # Parse JSON
        transactions = json.loads(llm_output)

        # Convert amounts to Decimal
        for transaction in transactions:
            transaction['amount'] = Decimal(str(transaction['amount']))

        return transactions

    def match_transaction(self, transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a matching unpaid booking using heuristics.

        Args:
            transaction: Transaction dict with date, amount, description, reference

        Returns:
            Dict with 'booking' and 'confidence' if match found, None otherwise
        """
        amount = transaction['amount']
        reference = transaction.get('reference', '').strip()
        description = transaction.get('description', '').strip()

        # Get all unpaid bookings for this event
        unpaid_bookings = Booking.objects.filter(
            event=self.event,
            is_paid=False
        )

        # Strategy 1: Exact amount + reference match
        if reference:
            # Check if reference appears in description or reference field
            for booking in unpaid_bookings:
                booking_ref = booking.payment_reference()
                if booking_ref.lower() in reference.lower() or booking_ref.lower() in description.lower():
                    if booking.donation_amount == amount:
                        return {
                            'booking': booking,
                            'confidence': 'high',
                            'reason': f'Exact match: amount £{amount} + reference {booking_ref}'
                        }

        # Strategy 2: Exact amount match (single match only)
        exact_amount_matches = [b for b in unpaid_bookings if b.donation_amount == amount]
        if len(exact_amount_matches) == 1:
            return {
                'booking': exact_amount_matches[0],
                'confidence': 'medium',
                'reason': f'Single booking with exact amount £{amount}'
            }

        # Strategy 3: Return multiple candidates for LLM suggestion
        if len(exact_amount_matches) > 1:
            return {
                'booking': None,
                'candidates': exact_amount_matches,
                'confidence': 'low',
                'reason': f'{len(exact_amount_matches)} bookings with amount £{amount} - needs review'
            }

        # No match found
        return None

    def llm_suggest_match(
        self,
        transaction: Dict[str, Any],
        candidates: List[Booking]
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to suggest the best match from multiple candidates.

        Args:
            transaction: Transaction dict
            candidates: List of candidate bookings

        Returns:
            Dict with 'booking' and 'confidence' if match found, None otherwise
        """
        # Prepare candidate info
        candidate_info = []
        for i, booking in enumerate(candidates, 1):
            candidate_info.append(
                f"{i}. Booking {booking.payment_reference()}: "
                f"{booking.full_name} ({booking.email}), "
                f"£{booking.donation_amount}, "
                f"{booking.num_tickets} ticket(s), "
                f"created {booking.created_at.strftime('%Y-%m-%d')}"
            )

        prompt = f"""You are helping match a bank transaction to a booking.

Transaction Details:
- Date: {transaction['date']}
- Amount: £{transaction['amount']}
- Description: {transaction['description']}
- Reference: {transaction.get('reference', 'N/A')}

Candidate Bookings:
{chr(10).join(candidate_info)}

Which booking is most likely to match this transaction? Consider:
- Name matches in description
- Email domain in description
- Reference codes
- Dates (transaction should be after booking creation)

Respond with ONLY a JSON object in this format:
{{"booking_number": <1-{len(candidates)} or 0 for no match>, "confidence": "<high/medium/low>", "reason": "<brief explanation>"}}
"""

        # Call LLM
        response = completion(
            model=self.llm_model,
            provider=self.llm_provider,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        llm_output = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if llm_output.startswith("```"):
            lines = llm_output.split("\n")
            llm_output = "\n".join(lines[1:-1])
        if llm_output.startswith("json"):
            llm_output = llm_output[4:].strip()

        result = json.loads(llm_output)

        booking_number = result.get('booking_number', 0)
        if booking_number > 0 and booking_number <= len(candidates):
            return {
                'booking': candidates[booking_number - 1],
                'confidence': result.get('confidence', 'low'),
                'reason': f"LLM suggestion: {result.get('reason', 'No reason provided')}"
            }

        return None

    def reconcile(self, csv_file) -> List[Dict[str, Any]]:
        """
        Main reconciliation workflow.

        Args:
            csv_file: Uploaded CSV file

        Returns:
            List of reconciliation results, each containing:
            - transaction: Original transaction dict
            - match: Match result (booking, confidence, reason) or None
        """
        # Stage 1: Parse CSV with LLM
        transactions = self.parse_csv_with_llm(csv_file)

        results = []

        # Stage 2 & 3: Match transactions
        for transaction in transactions:
            match_result = self.match_transaction(transaction)

            # If we have multiple candidates, use LLM to suggest
            if match_result and match_result.get('candidates'):
                llm_match = self.llm_suggest_match(
                    transaction,
                    match_result['candidates']
                )
                if llm_match:
                    match_result = llm_match
                else:
                    # Keep the candidates for manual review
                    match_result['booking'] = None

            results.append({
                'transaction': transaction,
                'match': match_result
            })

        return results
