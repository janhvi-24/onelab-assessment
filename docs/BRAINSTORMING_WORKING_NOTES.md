# Brainstorming thread — assessment working notes

**User problem:** A payments company's month-end books do not balance. The platform knows what it processed; the bank knows what it settled. Find and show the gaps.

**AI brainstorming response:**
I would treat this as a reconciliation and exception-management problem, not merely a file comparison. First define the two source datasets and their grain. Then define a cutoff date and a matching key. Finally, make every discrepancy visible and explainable.

**Questions considered**
- What is the primary matching key? Assumption: transaction ID.
- Can settlement occur after month end? Yes; classify it separately as next-month settlement.
- How should duplicates be treated? Flag them; do not silently deduplicate.
- How can rounding only appear after summing? Use multiple individually tolerated differences whose aggregate exceeds tolerance.
- What makes a refund orphaned? Its original payment reference is absent from the platform payment records.

**Approach selected**
- Build a small Streamlit app so a finance reviewer can upload CSVs and inspect exceptions.
- Use pandas for deterministic data handling.
- Use pytest for repeatable checks.
- Include seeded sample files so the assessor can reproduce the four required cases.
- Export the reconciliation and exception tables as CSV.

**Trade-offs**
- A simple Streamlit prototype is faster to inspect than a backend/API architecture.
- Transaction ID matching is easy to explain, but is not sufficient for all real processor settlement patterns.
- A fixed INR 0.01 tolerance makes the assessment reproducible, but production tolerance must be currency- and policy-aware.

**Outcome**
The prototype focuses on transparency: every exception has a category, record ID, related reference, amount and human-readable explanation.
