# 2-minute demo video script

1. (0:00–0:15) Introduce the problem: platform transactions and bank settlements should reconcile at month end.
2. (0:15–0:35) Open the app. Point out the November 30 cutoff and INR 0.01 tolerance. Explain that sample CSVs are loaded by default.
3. (0:35–1:15) Open Exceptions. Show the next-month settlement, duplicate settlement, orphan refund and aggregate rounding drift. Explain why each is flagged.
4. (1:15–1:40) Open Transaction matching. Show matched vs exceptional statuses and explain transaction-ID matching.
5. (1:40–1:55) Download the exceptions CSV and reconciliation CSV.
6. (1:55–2:00) State the production limitations: split/partial settlements, fees/FX, and missing audit/security/integration controls.
