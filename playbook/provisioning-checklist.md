# Provisioning Checklist

Standard steps per product tier, counted in business days from `signed_date`.
`owner` is either `cs` (StackAdapt-side) or `customer`.

## Enterprise tier

| # | Step                          | Owner    | Due (business days after signature) |
|---|--------------------------------|----------|---------------------------------------|
| 1 | Kickoff call scheduled          | cs       | 2  |
| 2 | Admin account provisioned       | cs       | 3  |
| 3 | SSO configuration submitted     | customer | 5  |
| 4 | Data import file submitted      | customer | 7  |
| 5 | Integration testing completed   | cs       | 10 |
| 6 | Go-live                         | cs       | 14 |

## Growth tier

| # | Step                          | Owner    | Due (business days after signature) |
|---|--------------------------------|----------|---------------------------------------|
| 1 | Kickoff call scheduled          | cs       | 2  |
| 2 | Admin account provisioned       | cs       | 3  |
| 3 | Data import file submitted      | customer | 5  |
| 4 | Go-live                         | cs       | 10 |

## Rules

- A step is **overdue** if today is past its `due_date` and `status` is not `done`.
- Overdue steps owned by `customer` are eligible for an autonomous nudge (see
  escalation-policy.md).
- Overdue steps owned by `cs` are never auto-remediated — they indicate an
  internal bottleneck and must be surfaced to a human.
