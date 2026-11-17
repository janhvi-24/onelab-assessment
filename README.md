# Onelab — Payment Reconciliation Intelligence

A Streamlit prototype for comparing payment-platform transactions with bank settlement records and explaining month-end reconciliation exceptions.

## Features

- Month-end cutoff date and configurable monetary tolerance.
- Upload platform-transaction and bank-settlement CSV files.
- Load the included sample data by default.
- Summary KPIs, transaction-level results, and exception details.
- CSV downloads for reconciliation results and exceptions.
- Input validation for required columns, IDs, dates, amounts, and currencies.
- Explicit handling of duplicate settlement transaction IDs.

## Project structure

```text
.
├── app.py                         # Streamlit user interface
├── reconciliation.py              # Reconciliation and validation logic
├── requirements.txt               # Python dependencies
├── data/
│   ├── transactions.csv            # Sample platform transactions
│   └── settlements.csv             # Sample bank settlement records
├── tests/
│   └── test_reconciliation.py      # Automated tests
└── docs/
    ├── COPILOT_RAW_PROMPT.txt
    ├── COPILOT_DISTILLED_PROMPT.txt
    ├── COPILOT_EXECUTION_THREAD_READABLE.md
    ├── TEST_CASES.md
    └── DEMO_VIDEO_SCRIPT.md
```

## Requirements

- Python 3.10 or newer (recommended).
- pip.

## Run locally

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit normally opens at `http://localhost:8501`.

## Run automated tests

```bash
python -m pytest -v
```

The Copilot execution session reported **8 tests passing**. Re-run the command locally before submission and retain the actual terminal output as evidence.

## Sample data and seeded assessment gaps

- `data/transactions.csv`: platform-side payment and refund events.
- `data/settlements.csv`: bank-side settlement rows.
- The sample data is intended to demonstrate all four required assessment scenarios:
  1. A transaction recorded before month-end but settled in the following month.
  2. Small individual rounding differences whose aggregate exceeds the configured tolerance.
  3. A duplicate record in the settlement dataset.
  4. A refund whose referenced original payment is absent.

Inspect the CSV files and the dashboard results to confirm the seeded examples are classified as intended.

## CSV schemas

**Platform transactions**

`transaction_id,event_type,original_transaction_id,amount,currency,transaction_date`

**Bank settlements**

`settlement_id,transaction_id,settlement_amount,currency,settlement_date`

Dates must be parseable. Amounts must be numeric. Use a consistent currency within a reconciliation run. The application should report invalid input rather than silently dropping malformed rows.

## Assumptions

1. The month-end cutoff is inclusive.
2. Transaction ID is the primary matching key.
3. Sample currency is INR.
4. The default monetary tolerance is INR 0.01; the UI may allow the user to change it.
5. A settlement after the cutoff is classified as a next-period settlement, not automatically as a failed payment.
6. A refund must reference an original payment present in the platform dataset.
7. An orphan refund with no bank row is classified as an orphan refund, not also as a missing settlement; valid transactions without a bank row remain missing settlements.
8. Duplicate settlement transaction IDs are exceptions and are not treated as clean one-to-one matches.
9. The sample focuses on gross amounts; processing fees and net settlement adjustments are out of scope.

## Architecture

- `app.py` contains the Streamlit presentation layer, upload controls, result views, and download actions.
- `reconciliation.py` contains the reusable reconciliation engine and input validation.
- `data/` contains deterministic sample CSV files.
- `tests/` contains automated tests for the reconciliation logic.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository and push the project files to its root.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) and connect GitHub.
3. Create an app using the repository, branch, and `app.py` as the main file.
4. Deploy the app.
5. Verify the public URL in a private/incognito browser before including it in the assessment submission.

Do not claim the application is deployed until the public URL has been tested.

## Three production limitations

1. The prototype assumes a stable one-to-one transaction-ID match; real processors may split, combine, retry, or partially settle transactions across multiple bank batches.
2. It uses a simplified tolerance and gross-amount model, so fees, foreign-exchange conversion, chargebacks, reversals, time zones, and currency-specific precision can create false positives or false matches.
3. It lacks production-grade access controls, immutable audit logs, approval workflows, encryption governance, and direct integrations with authoritative bank and processor systems.

## Known boundaries

This is an assessment prototype, not a general ledger or certified accounting system. Before production use, validate source schemas, date conventions, sign conventions, settlement semantics, currency handling, and exception workflows with the finance team.
