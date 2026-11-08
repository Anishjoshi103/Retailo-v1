# Branch GST identity

Each branch is a place of business and carries its own GST identity, because the
seller's state decides CGST/SGST versus IGST on sales documents.

## Fields

- `state_code` — two-digit GST state/UT code (`01`-`38`, `97`, `99`). Blank until set.
- `gstin` — optional 15-character GSTIN. When present its first two digits must equal `state_code`. A branch may be unregistered (blank GSTIN) but still needs a `state_code` to issue sales.

Several branches may share one GSTIN (additional places of business under one registration), so the GSTIN is not unique.

## API

`PATCH /api/v1/branches/{id}` with `gstin` and/or `state_code` (owner/admin only; see `rbac.md`).

- Sending only `gstin` derives `state_code` from its first two digits.
- Validation is format-based; the GSTIN check character is not verified.
- Unknown, foreign-tenant and ungranted branches all return 404.

`GET /api/v1/branches` and the branch list now include both fields.

## Follow-up

Sales issuance (next PRs) will refuse to post a sale for a branch with a blank `state_code`.
