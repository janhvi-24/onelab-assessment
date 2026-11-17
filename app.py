"""Streamlit interface for the Onelab payment reconciliation assessment."""

from pathlib import Path

import pandas as pd
import streamlit as st

from reconciliation import reconcile

st.set_page_config(
    page_title="Onelab | Payment Reconciliation",
    page_icon="💳",
    layout="wide",
)

BASE = Path(__file__).parent
DATA = BASE / "data"


def load_csv(upload, fallback: Path) -> pd.DataFrame:
    """Load identifiers as text so leading zeroes are not lost."""
    source = upload if upload is not None else fallback
    return pd.read_csv(source, dtype=str, keep_default_na=False)


def show_source_data(tx: pd.DataFrame, stl: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.markdown("**Platform transactions**")
        st.caption(f"{len(tx):,} source rows")
        st.dataframe(tx, use_container_width=True, hide_index=True)
    with right:
        st.markdown("**Bank settlements**")
        st.caption(f"{len(stl):,} source rows")
        st.dataframe(stl, use_container_width=True, hide_index=True)


st.title("💳 Onelab | Payment Reconciliation")
st.caption(
    "Compare platform transactions with bank settlements and review "
    "month-end exceptions."
)

with st.sidebar:
    st.header("Reconciliation settings")
    month_end = st.date_input(
        "Month-end cutoff (inclusive)",
        value=pd.Timestamp("2026-11-30").date(),
    )
    tolerance = st.number_input(
        "Row and aggregate tolerance (INR)",
        min_value=0.0,
        value=0.01,
        step=0.01,
        format="%.2f",
        help=(
            "A row difference at or below this value is provisionally matched. "
            "Accepted differences are also summed by currency."
        ),
    )
    st.divider()
    tx_upload = st.file_uploader("Platform transactions CSV", type="csv")
    st_upload = st.file_uploader("Bank settlements CSV", type="csv")
    st.caption("Included sample files load automatically when no file is uploaded.")

try:
    tx = load_csv(tx_upload, DATA / "transactions.csv")
    stl = load_csv(st_upload, DATA / "settlements.csv")
except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
    st.error(f"Could not read the uploaded CSV: {error}")
    st.stop()

try:
    result, issues = reconcile(tx, stl, month_end, tolerance)
except ValueError as error:
    st.error(str(error))
    st.subheader("Source data preview")
    show_source_data(tx, stl)
    st.stop()

clean_matches = int((result["status"] == "Matched").sum())
not_clean = len(result) - clean_matches
metric_columns = st.columns(4)
metric_columns[0].metric("Platform records in period", len(result))
metric_columns[1].metric("Clean matches", clean_matches)
metric_columns[2].metric("Transactions needing review", not_clean)
metric_columns[3].metric("Exception findings", len(issues))

with st.expander("How to read this reconciliation"):
    st.markdown(
        """
        - **Matched** means there is one settlement within the cutoff and its
          amount difference is within tolerance.
        - **Settled next month** means the platform transaction is in period,
          but its settlement date is after the cutoff.
        - Duplicate source IDs, orphan refunds, missing settlements, material
          amount differences, currency differences, and aggregate rounding drift
          are shown as separate findings.
        - A transaction with duplicate bank settlement rows is never counted
          as a clean one-to-one match; duplicate source rows are retained.
        """
    )

st.subheader("Reconciliation overview")
if result.empty:
    st.info("No platform transactions fall on or before the selected cutoff.")
else:
    status_counts = result["status"].value_counts().rename_axis("status")
    st.bar_chart(status_counts)

exceptions_tab, matching_tab, source_tab = st.tabs(
    ["Exceptions", "Transaction matching", "Source data"]
)
with exceptions_tab:
    st.subheader("Exception findings")
    if issues.empty:
        st.success("No issues detected under the selected assumptions.")
    else:
        st.dataframe(issues, use_container_width=True, hide_index=True)
        st.download_button(
            "Download exceptions CSV",
            data=issues.to_csv(index=False).encode("utf-8"),
            file_name="reconciliation_exceptions.csv",
            mime="text/csv",
        )

with matching_tab:
    st.subheader("Platform transactions in the selected period")
    st.dataframe(result, use_container_width=True, hide_index=True)
    st.download_button(
        "Download reconciliation CSV",
        data=result.to_csv(index=False).encode("utf-8"),
        file_name="reconciliation_results.csv",
        mime="text/csv",
    )

with source_tab:
    st.subheader("Uploaded or included source records")
    show_source_data(tx, stl)

with st.expander("Assumptions and known boundaries"):
    st.markdown(
        """
        - The cutoff is inclusive. Transaction ID is the primary matching key.
        - Sample data uses INR; the default row and aggregate tolerance is INR
          0.01.
        - A post-cutoff settlement is a next-period settlement, not necessarily
          a missing payment.
        - Refunds must reference an existing original payment in the platform
          file. Duplicate settlement IDs are exceptions, not clean matches.
        - This prototype does not model fees, partial settlements, foreign
          exchange, chargebacks, reversals, or bank-specific batch references.
        """
    )
