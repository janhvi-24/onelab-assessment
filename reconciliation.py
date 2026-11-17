"""Validation and reconciliation logic for platform and bank CSV data."""

import math
from datetime import date

import pandas as pd

REQUIRED_TX_COLUMNS = {
    "transaction_id",
    "event_type",
    "original_transaction_id",
    "amount",
    "currency",
    "transaction_date",
}
REQUIRED_ST_COLUMNS = {
    "settlement_id",
    "transaction_id",
    "settlement_amount",
    "currency",
    "settlement_date",
}
RESULT_COLUMNS = [
    "transaction_id",
    "transaction_amount",
    "settlement_amount",
    "difference",
    "status",
    "currency",
    "settlement_count",
]
ISSUE_COLUMNS = ["issue_type", "record_id", "related_id", "amount", "detail"]


def _validate_source(
    frame: pd.DataFrame,
    required_columns: set[str],
    date_column: str,
    amount_column: str,
    id_columns: tuple[str, ...],
    source_name: str,
) -> pd.DataFrame:
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(
            f"{source_name} CSV is missing required columns: "
            f"{', '.join(missing_columns)}."
        )

    clean = frame.copy()
    for column in id_columns:
        clean[column] = clean[column].astype("string").str.strip()

    dates = pd.to_datetime(clean[date_column], errors="coerce", format="mixed")
    invalid_dates = dates.isna()
    if invalid_dates.any():
        rows = [
            row_number
            for row_number, invalid in enumerate(invalid_dates.tolist(), start=2)
            if invalid
        ]
        raise ValueError(
            f"{source_name} CSV has missing or invalid {date_column} values "
            f"on data row(s): {_format_rows(rows)}."
        )
    clean[date_column] = dates

    amounts = pd.to_numeric(clean[amount_column], errors="coerce")
    invalid_amounts = amounts.isna() | ~amounts.map(
        lambda value: math.isfinite(float(value)) if pd.notna(value) else False
    )
    if invalid_amounts.any():
        rows = [
            row_number
            for row_number, invalid in enumerate(invalid_amounts.tolist(), start=2)
            if invalid
        ]
        raise ValueError(
            f"{source_name} CSV has missing, non-numeric, or non-finite "
            f"{amount_column} values on data row(s): {_format_rows(rows)}."
        )
    clean[amount_column] = amounts.astype(float)

    for column in id_columns:
        invalid_ids = clean[column].isna() | clean[column].eq("")
        if invalid_ids.any():
            rows = [
                row_number
                for row_number, invalid in enumerate(invalid_ids.tolist(), start=2)
                if invalid
            ]
            raise ValueError(
                f"{source_name} CSV has empty {column} values on data row(s): "
                f"{_format_rows(rows)}."
            )

    clean["currency"] = clean["currency"].astype("string").str.strip().str.upper()
    if clean["currency"].isna().any() or clean["currency"].eq("").any():
        invalid_currencies = clean["currency"].isna() | clean["currency"].eq("")
        rows = [
            row_number
            for row_number, invalid in enumerate(invalid_currencies.tolist(), start=2)
            if invalid
        ]
        raise ValueError(
            f"{source_name} CSV has empty currency values on data row(s): "
            f"{_format_rows(rows)}."
        )
    if "original_transaction_id" in clean.columns:
        clean["original_transaction_id"] = (
            clean["original_transaction_id"].astype("string").fillna("").str.strip()
        )
    return clean


def _format_rows(rows: list[int]) -> str:
    return ", ".join(str(row) for row in rows)


def reconcile(
    tx: pd.DataFrame,
    stl: pd.DataFrame,
    cutoff: date,
    tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconcile platform transactions with bank settlements by transaction ID.

    Invalid input raises a descriptive ValueError instead of being silently
    excluded from the reconciliation.
    """
    if not math.isfinite(float(tolerance)) or tolerance < 0:
        raise ValueError("Tolerance must be a finite, non-negative amount.")

    tx = _validate_source(
        tx,
        REQUIRED_TX_COLUMNS,
        "transaction_date",
        "amount",
        ("transaction_id", "event_type"),
        "Platform transactions",
    )
    stl = _validate_source(
        stl,
        REQUIRED_ST_COLUMNS,
        "settlement_date",
        "settlement_amount",
        ("settlement_id", "transaction_id"),
        "Bank settlements",
    )
    tx["event_type"] = tx["event_type"].str.lower()

    issues: list[dict[str, object]] = []
    payment_ids = set(
        tx.loc[tx["event_type"] == "payment", "transaction_id"].astype(str)
    )
    in_scope = tx[tx["transaction_date"].dt.date <= cutoff]

    orphan_refund_ids: set[str] = set()
    for _, row in in_scope[in_scope["event_type"] == "refund"].iterrows():
        original = str(row["original_transaction_id"]).strip()
        if not original or original not in payment_ids:
            orphan_refund_ids.add(str(row["transaction_id"]))
            issues.append(
                {
                    "issue_type": "Orphan refund",
                    "record_id": row["transaction_id"],
                    "related_id": original or "Missing",
                    "amount": row["amount"],
                    "detail": (
                        "Refund has no matching original payment in the "
                        "transaction dataset."
                    ),
                }
            )

    tx_counts = tx["transaction_id"].value_counts()
    duplicate_tx_ids = set(tx_counts[tx_counts > 1].index.astype(str))
    for transaction_id in sorted(duplicate_tx_ids):
        matching = tx[tx["transaction_id"] == transaction_id]
        for _, row in matching.iterrows():
            issues.append(
                {
                    "issue_type": "Duplicate transaction",
                    "record_id": transaction_id,
                    "related_id": "Transaction dataset",
                    "amount": row["amount"],
                    "detail": (
                        "Transaction ID appears more than once in the "
                        "platform dataset."
                    ),
                }
            )

    settlement_groups = {
        str(transaction_id): group
        for transaction_id, group in stl.groupby("transaction_id", sort=False)
    }
    duplicate_settlements = {
        transaction_id: group
        for transaction_id, group in settlement_groups.items()
        if len(group) > 1
    }
    for transaction_id, group in duplicate_settlements.items():
        issues.append(
            {
                "issue_type": "Duplicate settlement",
                "record_id": transaction_id,
                "related_id": ", ".join(group["settlement_id"].astype(str)),
                "amount": group["settlement_amount"].sum(),
                "detail": (
                    f"{len(group)} settlement rows reference the same "
                    "transaction ID."
                ),
            }
        )

    rows: list[dict[str, object]] = []
    aggregate_rounding: list[tuple[str, float, str]] = []
    for _, row in in_scope.iterrows():
        transaction_id = str(row["transaction_id"])
        matches = settlement_groups.get(transaction_id)
        settlement_count = 0 if matches is None else len(matches)

        if transaction_id in duplicate_tx_ids:
            status = "Duplicate transaction"
            settlement_amount = None
            difference = None
        elif transaction_id in duplicate_settlements:
            status = "Duplicate settlement"
            settlement_amount = matches["settlement_amount"].sum()
            difference = None
        else:
            in_period_matches = (
                matches[matches["settlement_date"].dt.date <= cutoff]
                if matches is not None
                else None
            )
            if in_period_matches is None or in_period_matches.empty:
                future_matches = (
                    matches[matches["settlement_date"].dt.date > cutoff]
                    if matches is not None
                    else None
                )
                if future_matches is not None and not future_matches.empty:
                    status = "Settled next month"
                    settlement_issue = {
                        "issue_type": "Next-month settlement",
                        "record_id": transaction_id,
                        "related_id": "After cutoff",
                        "amount": row["amount"],
                        "detail": (
                            "Platform transaction is in period; bank settlement "
                            "is after the month-end cutoff."
                        ),
                    }
                elif transaction_id in orphan_refund_ids:
                    status = "Orphan refund"
                    settlement_issue = None
                else:
                    status = "Missing settlement"
                    settlement_issue = {
                        "issue_type": "Missing settlement",
                        "record_id": transaction_id,
                        "related_id": "No bank row",
                        "amount": row["amount"],
                        "detail": "No settlement row was found for this transaction.",
                    }
                settlement_amount = None
                difference = None
                if settlement_issue is not None:
                    issues.append(settlement_issue)
            else:
                settlement = in_period_matches.iloc[0]
                settlement_amount = settlement["settlement_amount"]
                settlement_currency = settlement["currency"]
                difference = round(float(row["amount"] - settlement_amount), 6)
                if row["currency"] != settlement_currency:
                    status = "Currency mismatch"
                    difference = None
                    issues.append(
                        {
                            "issue_type": "Currency mismatch",
                            "record_id": transaction_id,
                            "related_id": settlement_currency,
                            "amount": None,
                            "detail": (
                                f"Platform currency {row['currency']} differs "
                                f"from settlement currency {settlement_currency}."
                            ),
                        }
                    )
                elif abs(difference) <= tolerance:
                    status = "Matched"
                    if difference != 0:
                        aggregate_rounding.append(
                            (transaction_id, difference, str(row["currency"]))
                        )
                else:
                    status = "Amount mismatch"
                    issues.append(
                        {
                            "issue_type": "Amount mismatch",
                            "record_id": transaction_id,
                            "related_id": "Bank amount",
                            "amount": difference,
                            "detail": (
                                "Transaction and settlement amounts differ "
                                "beyond the configured row tolerance."
                            ),
                        }
                    )

        rows.append(
            {
                "transaction_id": transaction_id,
                "transaction_amount": row["amount"],
                "settlement_amount": settlement_amount,
                "difference": difference,
                "status": status,
                "currency": row["currency"],
                "settlement_count": settlement_count,
            }
        )

    if aggregate_rounding:
        rounding = pd.DataFrame(
            aggregate_rounding, columns=["transaction_id", "difference", "currency"]
        )
        for currency, group in rounding.groupby("currency", sort=True):
            total = round(float(group["difference"].sum()), 6)
            if abs(total) > tolerance:
                issues.append(
                    {
                        "issue_type": "Aggregate rounding drift",
                        "record_id": f"{len(group)} transactions",
                        "related_id": currency,
                        "amount": total,
                        "detail": (
                            "Each row is within tolerance, but the summed "
                            f"difference ({total:.6f}) exceeds tolerance "
                            f"({tolerance:.2f})."
                        ),
                    }
                )

    result = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    issue_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    return result, issue_df
