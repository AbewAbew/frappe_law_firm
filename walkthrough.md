# IP Management Walkthrough

## Current Process

IP work is managed through IP Cases, dated stage fields, Trademark Owners, Patent Applications, and Legal Bills. IP Task, IP Request Type, and IP Workflow Rule have been retired because the firm uses each IP Case as the single operational record.

## Roles

| Role | Main access |
|---|---|
| IP Manager | Manages IP Cases; creates draft IP invoices |
| IP Staff | Works on IP Cases; cannot create IP invoices |
| Legal Finance | Reads linked IP Cases and completes Legal Bills |
| HR Manager | Same IP billing-review access as Legal Finance |
| System Manager | Full configuration and troubleshooting access |

## Cases and Deadlines

Create an IP Case using the correct Case Type: New Trademark, Trademark Renewal, Recordals, or Disputes & Surrenders. Enter the actual filing, advertisement, opposition, registration, office-action, and renewal dates as the matter progresses.

The form calculates the related deadline fields and displays them in the deadline dashboard. The daily scheduled job uses those stored dates to send Case-linked emails:

- 90 days before a pending Trademark Renewal Due Date;
- 14 days before an unpaid Registration Fee Due Date;
- seven days before, one day before, and on the due date for the standard IP and Office Action deadlines.

Status changes continue to create status-history rows, but they do not create separate rule-based deadlines or tasks.

## Patent Applications

Patent Application uses controlled status actions instead of a configurable Workflow. IP Manager and System Manager can move a saved application through the provisional sequence Draft, Filed, Formal Exam, Substantive Exam, Published, Granted, and Expired. Refused, Withdrawn, and Surrendered exits are available where applicable. Direct status edits and invalid jumps are rejected server-side, and each transition is recorded in Status History.

The system requires the filing documents before Filed and the corresponding formal examination, substantive examination, publication, grant, or expiration date before entering that stage. The firm must confirm the provisional sequence after its operational review; revise the transition map if the authority's actual process differs.

## Billing

The IP Manager creates a draft bill from the relevant stage button. Each stage uses two configured Legal Service Items: the official fee and the professional fee. Both items must have a non-zero Standard Rate before invoice creation succeeds.

The bill inherits the IP Case payer and currency. Supporting stage documents are attached to the Legal Bill. Only one bill can be generated for the same IP Case and billing stage. Legal Finance or HR Manager then reviews and completes the invoice.

## Administration Checks

1. Confirm the scheduler and workers are healthy.
2. Confirm Case Lead Email is populated for deadline emails.
3. Configure all IP Legal Service Item rates before billing.
4. Test each billing stage with IP Manager, IP Staff, and Legal Finance accounts.
5. Confirm completed stages have their dates, checkboxes, and supporting evidence updated on the IP Case.
6. Do not recreate IP Task, IP Request Type, or IP Workflow Rule; they are not part of the current process.
