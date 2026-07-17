# Invoicing Policy

1. **Issuance window.** Once a contract is signed, NetSuite must issue the invoice
   within **5 business days**. If more than 5 business days have passed since
   `signed_date` and `invoice_status` is still `not_created`, this is a policy
   breach and should be flagged as a risk.

2. **Payment window.** Once an invoice is issued, payment is expected within
   **15 calendar days** of `issued_date`. If more than 15 days have passed and
   `invoice_status` is still `issued` (not `paid`), this is a policy breach and
   should be flagged as a risk.

3. **Ownership.** Invoice issuance is a **CS/Finance-owned** action. Payment is a
   **customer-owned** action. Neither is on the autonomous action allowlist —
   both breaches should be surfaced to a human, never auto-remediated.
