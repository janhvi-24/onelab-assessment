# Test cases

| ID | Scenario | Input setup | Expected result |
|---|---|---|---|
| TC-01 | Exact match | Same transaction ID and amount on both sides | Status is `Matched` |
| TC-02 | Next-month settlement | Transaction dated on/before Nov 30; settlement dated Dec 1 | `Next-month settlement` exception |
| TC-03 | Aggregate rounding | Three rows differ by INR 0.004 each; row tolerance INR 0.01 | Each row is accepted as matched; aggregate drift of INR 0.012 is reported |
| TC-04 | Duplicate bank entry | Two settlement rows share one transaction ID | `Duplicate settlement` exception; not cleanly matched |
| TC-05 | Orphan refund | Refund references an original transaction ID absent from payments | `Orphan refund` exception |
| TC-06 | Missing settlement | No settlement row exists, including after cutoff | `Missing settlement` exception |
| TC-07 | Amount mismatch | Difference exceeds configured tolerance | `Amount mismatch` exception |
| TC-08 | Schema validation | Remove a required CSV column | UI displays a schema error and stops processing |
| TC-09 | Date validation | Include an unparseable date | Record should be reviewed; current prototype may exclude NaT dates from cutoff filtering (production hardening required) |

Run automated tests using `pytest -q`.
