# DECISIONS.md — Engineering & Product Decision Log

Each entry follows: **Decision → Options considered → Why we chose it → Trade-offs accepted**

---

## D-01: USD → INR Exchange Rate

**Decision**: Use a static rate of **₹95 per USD**, configured in `settings.py` as `USD_TO_INR_RATE`.

**Options considered**:
1. Live rate via a public API (e.g. exchangerate-api.com)
2. Static rate set at import time
3. Store original USD amount and show both; convert only for balance comparisons

**Why static**: The assignment explicitly states this is a shared expense tracker for a flatmate group during a specific trip (Goa, March 2026). Historical balance calculations must be **deterministic and reproducible** — if the rate changed, the same import would produce different balances. A live rate also requires a network dependency and API key, which complicates setup. The Goa trip occurred in March 2026; ₹95/USD was a realistic rate for that period.

**Trade-off accepted**: The rate will drift over time. Documented in `SCOPE.md` so anyone reviewing the app understands this is a deliberate choice, not an oversight. The rate is in one place (`settings.USD_TO_INR_RATE`) and trivial to change.

**Where enforced**: `expenses/splits.py → convert_to_inr()`, called by both the importer and the live balance calculator.

---

## D-02: Temporal Membership Model

**Decision**: `GroupMembership` has `joined_at` (DATE, required) and `left_at` (DATE, nullable). An expense dated `D` includes member `M` if and only if `M.joined_at <= D` and (`M.left_at IS NULL` or `D <= M.left_at`).

**Options considered**:
1. Boolean `is_active` flag — simple, but loses history
2. Date range on membership — chosen approach
3. Separate `MembershipEvent` table with event types (join/leave)

**Why date range**: Simpler schema than option 3, still captures the full question "was this person a member on this date?" Option 1 doesn't answer historical questions at all — if Meera's `is_active` is set to False today, we can't reconstruct her membership end date.

**Trade-off accepted**: Does not model re-joining (e.g., a member leaves and comes back). The assignment scenario doesn't require this; if needed, a `MembershipEvent` table would be the next step.

**Enforced in**:
- `expenses/importer.py → is_member_active_on_date()` — used during CSV import to remove departed members from splits
- `expenses/views.py → group_balances()` — filters `ExpenseSplit` records by member timeline

---

## D-03: Debt Simplification Algorithm

**Decision**: Use a **greedy min-heap algorithm** to minimize the number of transactions needed to settle all debts.

**Algorithm** (in `expenses/balances.py → simplify_debts()`):
1. Compute net balance for each member: `net = total_paid - total_owed`
2. Split into creditors (net > 0) and debtors (net < 0)
3. Greedy matching: largest debtor pays largest creditor; repeat until all settled

**Options considered**:
1. N² pairwise: every debtor pays every creditor directly → O(n²) transactions
2. Greedy (chosen) → O(n log n), produces at most n-1 transactions
3. Optimal min-transaction algorithm (NP-hard in general) — not needed for ≤ 10 members

**Why greedy**: For the flatmate scenario (≤ 7 members), greedy produces optimal or near-optimal results. The NP-hard optimal solution is not worth the complexity for a group this size. The greedy approach is transparent and explainable in the live session.

**Trade-off accepted**: Not guaranteed globally optimal for large groups, but optimal for all cases tested (7 members).

---

## D-04: Negative Amount Policy (Row 26)

**Decision**: Treat negative amounts as **refunds**, not errors.

**Options considered**:
1. Reject as error → crashes the import; loses economic information
2. Treat as refund, store `abs(amount)` with `is_refund=True` → chosen
3. Silently ignore → loses information

**Why refund**: Row 26 in the CSV is a parasailing refund (`-$30`). This is a real economic event — participants got money back. Ignoring it or crashing on it are both wrong. The split engine negates the share for each participant when `is_refund=True`, correctly crediting them.

**Where enforced**: `expenses/importer.py` (lines ~368-379), `expenses/splits.py → calculate_split()`.

---

## D-05: Conflicting Duplicate Tie-Break (Rows 24/25)

**Decision**: When two rows describe the same event with different amounts, keep the **later entry that contains a corrective note**. Earlier entry is skipped.

**Options considered**:
1. Keep the row with the higher amount (arbitrary)
2. Keep the row with the lower amount (arbitrary)
3. Keep both and flag both for manual resolution → user must pick
4. Keep the later row with a corrective note → chosen

**Why note-based tie-break**: Row 25 explicitly states "Aisha also logged this I think hers is wrong." This is unambiguous human intent. A purely mechanical rule (higher/lower) ignores available information. The corrective-note rule is deterministic and respects what the user wrote.

**Trade-off accepted**: If neither row has a corrective note, both are flagged as `conflicting_duplicate / needs_review` and the user must resolve manually. This is correct behavior — we don't guess.

---

## D-06: Missing Payer Policy (Row 13)

**Decision**: Flag as `needs_review` and **do not import** until the user assigns a payer. The row is NOT silently skipped and NOT silently assigned to any person.

**Options considered**:
1. Skip the row silently → loses the expense entirely
2. Assign payer = "Unknown" and split equally → creates phantom debt
3. Flag needs_review, block import of this row → chosen

**Why block**: A payer is necessary to compute who is owed money. There is no principled way to guess. The user knows their flatmates; we don't. The UI exposes a payer-assignment dropdown specifically for this row.

---

## D-07: Percentage Normalization (Rows 15, 32)

**Decision**: When percentages don't sum to 100%, **normalize proportionally**, then flag `needs_review`.

**Example**: Row 15: 30+30+30+20 = 110%. Each share becomes `original% / 110 * 100`.

**Options considered**:
1. Reject the row as an error → too aggressive for a data quality issue
2. Normalize silently → user doesn't know their data was altered
3. Normalize + flag needs_review → chosen
4. Keep as-is and cap at 100% → distorts relative shares

**Why normalize + flag**: Normalization makes mathematical sense (shares must sum to 100%). Flagging preserves transparency. A silent correction violates Meera's requirement: "I want to approve anything the app changes."

---

## D-08: JWT Authentication vs Django Sessions

**Decision**: Custom **JWT authentication** (PyJWT) with `Authorization: Bearer <token>` header.

**Options considered**:
1. Django sessions (cookie-based) → stateful, requires session storage
2. Django REST Framework's token auth (`rest_framework.authtoken`) → simpler but requires DB lookup on every request
3. JWT (stateless) → chosen

**Why JWT**: The React SPA communicates with the API over CORS. Cookies require `SameSite` configuration and CSRF tokens. JWT is the standard for SPA + REST API scenarios. Tokens expire after 30 days (configurable in settings).

**Trade-off accepted**: JWT tokens cannot be revoked before expiry without a blocklist. Acceptable for a flatmate app with no adversarial users.

---

## D-09: Frontend: Single-Page Split vs Tab-Per-Feature

**Decision**: Single `GroupDetailPage` with **5 tabs** (Balances, Expenses, Settlements, Members, Import) rather than separate routes per feature.

**Options considered**:
1. Separate routes: `/groups/<id>/expenses`, `/groups/<id>/balances`, etc.
2. Tabs within a single route → chosen

**Why tabs**: The flatmate context means users jump frequently between "how much do I owe?" (Balances) and "which expense is that?" (Expenses drill-down). Separate routes add navigation friction. All data is fetched in parallel on mount, making tab switches instant.

---

## D-10: Split Engine — Remainder Rounding

**Decision**: For equal splits, the rounding remainder (e.g., ₹100 ÷ 3 = 33.33…) is added to the **first participant's share**, ensuring the total is always exact.

**Options considered**:
1. Add remainder to random participant → non-deterministic
2. Add to payer → confused semantics
3. Add to first participant in list → chosen (deterministic, simple, auditable)

**Why first participant**: Deterministic and predictable. The split list is sorted by user ID, so the same participant always absorbs the rounding difference for a given expense. This means the total of all shares always equals the expense amount — no penny goes missing.

**Where enforced**: `expenses/splits.py → calculate_split()` lines ~45-65.
