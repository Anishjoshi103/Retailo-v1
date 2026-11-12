# Staff management

Owners and administrators add people to the store, choose their role and branches, and can
deactivate them. The staff screen in the app is the next PR; this document covers the API.

## Rules

| Who | May add / change |
|---|---|
| Owner | admin, manager, cashier, accountant |
| Admin | manager, cashier, accountant |
| Anyone else | nothing (403) |

- **Nobody can create an owner**, and nobody can change their own access (role, branches or
  active status), so a store can never lock itself out.
- An admin cannot change another admin or the owner.
- A member always needs at least one branch. Branches can only be granted from the caller's
  own grants. When a member also holds branches the caller cannot see, an edit leaves those alone.
- Members of other stores are never visible; they return 404.

## Endpoints

- `GET /api/v1/staff`: members with `id` (the membership id), `email`, `display_name`, `role`,
  `is_active`, `invited` (no password set yet), `branch_ids`, `is_self`, `can_manage`, `created_at`.
- `POST /api/v1/staff` `{email, role, branch_ids, display_name?}`: creates the person and emails
  them a link to set their password. Returns 201 with `invite_sent`; if the email could not be
  sent the person still exists and the invitation can be resent. An email that already has an
  account (in any store) returns 409.
- `PATCH /api/v1/staff/{id}` `{role?, branch_ids?, is_active?}`.
- `POST /api/v1/staff/{id}/resend-invite`: only while the person has not set a password (else 409).

## How invitations work

The new account is active but has **no usable password**, so nobody can sign in as it until the
emailed link (the same signed token the password-reset flow uses) is used. Opening the link
proves the person owns the mailbox, and the existing set-password page is reused. The link is
valid for the password-reset window (3 days by default); after that the person can use
"Forgot password" with the same address.

## Deactivation

Deactivating a membership blocks the person immediately: every request re-checks the
membership, so an access token that is still unexpired stops working at once, refresh fails,
and sign-in returns "not assigned to an active store". Reactivating restores access. Nothing is
deleted, so past sales still show who made them.

## Known limits

- One store per login: sign-in always picks the user's oldest active store, so an email that
  already has an account is refused rather than given a second store it could not switch to.
- No rate limiting on invitations yet (the API has no throttling at all; tracked separately).
- Changes are logged (actor, member, fields) but there is no audit trail screen yet.
