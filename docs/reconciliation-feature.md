# Bank Statement Reconciliation - Implementation Walkthrough

## Overview
Successfully implemented a bank statement reconciliation feature that allows administrators to upload bank CSV files and automatically match transactions against unpaid bookings using LLM-powered parsing and intelligent heuristics.

## What Was Built

### Core Components

#### 1. ReconciliationService ([reconciliation.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/reconciliation.py))
A comprehensive service class implementing a three-stage matching process:

**Stage 1: LLM-Powered CSV Parsing**
- Uses `any-llm-sdk` to parse varying bank statement formats
- Handles different column names and structures from different banks
- Normalizes data into standard JSON format: `{date, amount, description, reference}`
- Filters for incoming transactions only (credits/deposits)

**Stage 2: Heuristic Matching**
- **High confidence**: Exact amount + reference match (e.g., "TST-123" in description)
- **Medium confidence**: Unique booking with exact amount match
- **Low confidence**: Multiple candidates with same amount → requires LLM review

**Stage 3: LLM Suggestion**
- For ambiguous cases, LLM analyzes transaction details vs candidate bookings
- Considers name matches, email domains, dates, and reference codes
- Returns confidence score and reasoning

#### 2. ReconciliationView ([views.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/views.py#L240-L347))
Handles the web interface workflow:
- CSV file upload with LLM provider selection (OpenAI, Anthropic, Mistral)
- Session-based storage of parsed transactions
- Interactive confirmation of matches
- Automatic removal of confirmed transactions from review queue

#### 3. Template ([reconciliation.html](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/templates/tickets/reconciliation.html))
Clean, responsive UI featuring:
- File upload form with LLM provider selector
- Results table with transaction details
- Confidence indicators (High/Medium/Low badges)
- One-click confirmation buttons
- Expandable details for multiple candidates

#### 4. Comprehensive Tests ([test_reconciliation.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/tests/test_reconciliation.py))
7 passing tests covering:
- ✅ LLM CSV parsing (mocked)
- ✅ Exact match with reference
- ✅ Single amount match
- ✅ Multiple candidates detection
- ✅ No match scenarios
- ✅ LLM suggestion logic
- ✅ Full reconciliation workflow

## Files Changed

### New Files
- [tickets/reconciliation.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/reconciliation.py) - ReconciliationService class
- [tickets/templates/tickets/reconciliation.html](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/templates/tickets/reconciliation.html) - UI template
- [tickets/tests/test_reconciliation.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/tests/test_reconciliation.py) - Test suite
- [tickets/tests/__init__.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/tests/__init__.py) - Tests package initializer

### Modified Files
- [pyproject.toml](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/pyproject.toml#L12) - Added `any-llm-sdk[all]>=1.2.0`
- [tickets/views.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/views.py#L240-L347) - Added ReconciliationView
- [tickets/urls.py](file:///Users/tom/Documents/code/python/tickets-app/trusted-tickets/tickets/urls.py#L35-L39) - Added reconciliation route

## Verification Results

### Automated Testing
```bash
python manage.py test tickets.tests.test_reconciliation
```
**Result**: ✅ **All 7 tests passed** in 0.013s

Tests verified:
- CSV parsing with LLM integration
- Heuristic matching algorithms
- LLM suggestion for ambiguous matches
- End-to-end reconciliation workflow
- Edge cases (no matches, multiple candidates)

## How to Use

### Setup
1. **Install Dependencies**:
   ```bash
   source .venv/bin/activate
   uv pip install -e .
   ```

2. **Set LLM API Key** (choose one):
   ```bash
   export OPENAI_API_KEY="your-key"
   export ANTHROPIC_API_KEY="your-key"
   export MISTRAL_API_KEY="your-key"
   ```

### Usage
1. **Access Reconciliation Page**:
   - Navigate to: `https://yourdomain.com/<event-slug>/reconciliation/`
   - Requires staff login

2. **Upload CSV**:
   - Select your LLM provider (OpenAI, Anthropic, or Mistral)
   - Upload bank statement CSV file
   - Click "Parse & Match"

3. **Review Matches**:
   - **High confidence** (green): Reference + amount match
   - **Medium confidence** (amber): Unique amount match
   - **Low confidence** (red): Multiple candidates or uncertain

4. **Confirm Payments**:
   - Click "Confirm" button for valid matches
   - Booking is marked as `is_paid = True`
   - Transaction removed from review queue

5. **Re-upload Safe**:
   - Already-paid bookings won't be matched again
   - Safe to re-upload same CSV file

## Key Design Decisions

### Why LLM for CSV Parsing?
Different banks export CSVs with varying formats:
- Different column names ("Date" vs "Transaction Date")
- Different amount formats (positive/negative for credits)
- Different reference field locations

The LLM adapts to any format automatically.

### Why No Transaction Storage?
User feedback confirmed transactions don't need persistence:
- Reconciliation is a one-time review process
- Session storage is sufficient
- Simpler data model
- No migration needed

### Why Three-Stage Matching?
1. **Heuristics first**: Fast, deterministic, free
2. **LLM for ambiguity**: Only when needed, reduces API costs
3. **Human confirmation**: Final safety check

## Next Steps (Manual Testing)

To manually test the feature:

1. **Create test bookings**:
   - Log into Django admin
   - Create 2-3 unpaid bookings with different amounts

2. **Create sample CSV**:
   ```csv
   Date,Amount,Description
   2025-01-15,10.00,Transfer from John Smith TST-1
   2025-01-16,25.50,Payment received
   ```

3. **Test reconciliation**:
   - Go to `/<event-slug>/reconciliation/`
   - Upload the CSV
   - Verify matches appear with correct confidence levels
   - Click "Confirm" and verify booking status updates

4. **Test edge cases**:
   - Upload CSV with no matching amounts
   - Upload CSV with same amount as multiple bookings
   - Re-upload same CSV (should skip already-paid bookings)

## Summary

✅ **Feature Complete**: All planned functionality implemented
✅ **Tests Passing**: 7/7 automated tests successful  
✅ **Dependencies Added**: `any-llm-sdk[all]>=1.2.0` installed
✅ **Documentation**: Usage instructions included in this walkthrough
