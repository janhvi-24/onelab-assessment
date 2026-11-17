from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from reconciliation import reconcile

DATA_DIR = Path(__file__).parents[1] / "data"
CUTOFF = date(2026, 11, 30)


@pytest.fixture
def sample_data():
    transactions = pd.read_csv(DATA_DIR / "transactions.csv")
    settlements = pd.read_csv(DATA_DIR / "settlements.csv")
    return transactions, settlements


def test_seeded_transaction_is_settled_after_cutoff(sample_data):
    transactions, settlements = sample_data
    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    row = result.loc[result["transaction_id"] == "TXN-1006"].iloc[0]
    assert row["status"] == "Settled next month"
    assert "Next-month settlement" in set(issues["issue_type"])


def test_seeded_rounding_drift_exceeds_aggregate_tolerance(sample_data):
    transactions, settlements = sample_data
    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    small_differences = result[result["transaction_id"].isin(
        ["TXN-1003", "TXN-1004", "TXN-1005"]
    )]
    assert set(small_differences["status"]) == {"Matched"}
    assert all(small_differences["difference"].abs() <= 0.01)
    drift = issues.loc[issues["issue_type"] == "Aggregate rounding drift"].iloc[0]
    assert drift["amount"] == pytest.approx(0.012)


def test_seeded_duplicate_bank_row_is_not_a_clean_match(sample_data):
    transactions, settlements = sample_data
    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    row = result.loc[result["transaction_id"] == "TXN-1002"].iloc[0]
    assert row["status"] == "Duplicate settlement"
    assert row["settlement_count"] == 2
    assert "Duplicate settlement" in set(issues["issue_type"])


def test_seeded_refund_with_unknown_original_is_reported(sample_data):
    transactions, settlements = sample_data
    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    orphan = issues.loc[issues["issue_type"] == "Orphan refund"]
    assert "REF-2001" in set(orphan["record_id"])
    refund_issues = issues.loc[issues["record_id"] == "REF-2001"]
    assert list(refund_issues["issue_type"]) == ["Orphan refund"]
    row = result.loc[result["transaction_id"] == "REF-2001"].iloc[0]
    assert row["status"] == "Orphan refund"


def test_genuine_missing_payment_settlement_is_still_reported(sample_data):
    transactions, settlements = sample_data
    settlements = settlements.loc[
        settlements["transaction_id"] != "TXN-1008"
    ].copy()

    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    row = result.loc[result["transaction_id"] == "TXN-1008"].iloc[0]
    assert row["status"] == "Missing settlement"
    missing = issues.loc[
        (issues["issue_type"] == "Missing settlement")
        & (issues["record_id"] == "TXN-1008")
    ]
    assert len(missing) == 1


def test_exact_one_to_one_match_is_clean():
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "PAY-1",
                "event_type": "payment",
                "original_transaction_id": "",
                "amount": 125.00,
                "currency": "INR",
                "transaction_date": "2026-11-30",
            }
        ]
    )
    settlements = pd.DataFrame(
        [
            {
                "settlement_id": "SET-1",
                "transaction_id": "PAY-1",
                "settlement_amount": 125.00,
                "currency": "INR",
                "settlement_date": "2026-11-30",
            }
        ]
    )

    result, issues = reconcile(transactions, settlements, CUTOFF, 0.01)

    assert result.iloc[0]["status"] == "Matched"
    assert issues.empty


@pytest.mark.parametrize(
    ("column", "bad_value", "message"),
    [
        ("transaction_date", "not-a-date", "transaction_date"),
        ("amount", "not-an-amount", "amount"),
    ],
)
def test_invalid_platform_values_raise_actionable_error(
    sample_data, column, bad_value, message
):
    transactions, settlements = sample_data
    transactions[column] = transactions[column].astype("object")
    transactions.loc[0, column] = bad_value

    with pytest.raises(ValueError, match=message):
        reconcile(transactions, settlements, CUTOFF, 0.01)


def test_missing_required_column_is_reported(sample_data):
    transactions, settlements = sample_data
    transactions = transactions.drop(columns=["currency"])

    with pytest.raises(ValueError, match="currency"):
        reconcile(transactions, settlements, CUTOFF, 0.01)
