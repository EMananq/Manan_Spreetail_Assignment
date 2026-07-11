# SCOPE.md — Anomaly Log & Database Schema

## Part 1: Database Schema

### Core Models

#### `User` (custom AbstractBaseUser)
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | Auto-increment |
| email | VARCHAR(255) UNIQUE | Login identifier |
| name | VARCHAR(255) | Display name |
| password | VARCHAR | bcrypt-hashed by Django |
| created_at | TIMESTAMPTZ | |

#### `Group`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| name | VARCHAR(200) | |
| description | TEXT | |
| default_currency | CHAR(3) | INR / USD |
| created_at | TIMESTAMPTZ | |

#### `GroupMembership`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| group_id | FK → Group | |
| user_id | FK → User | |
| joined_at | DATE | Determines temporal inclusion |
| left_at | DATE NULL | NULL = still active |
| role | VARCHAR | member / admin |

**Temporal logic**: An expense dated `D` includes member `M` only if `M.joined_at <= D <= M.left_at` (or `left_at IS NULL`). This handles both Sam (joined Apr 8) and Meera (left Mar 31).

#### `Expense`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| group_id | FK → Group | |
| paid_by_id | FK → User | Who fronted the cash |
| description | VARCHAR(500) | |
| amount | DECIMAL(12,2) | Always stored as positive; refunds flagged separately |
| currency | CHAR(3) | INR or USD |
| split_type | VARCHAR | equal / unequal / percentage / share |
| expense_date | DATE | |
| notes | TEXT | |
| status | VARCHAR | active / skipped / needs_review |
| import_row_number | INT NULL | CSV row for traceability |
| created_at | TIMESTAMPTZ | |

#### `ExpenseSplit`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| expense_id | FK → Expense | |
| user_id | FK → User | Participant |
| amount | DECIMAL(12,2) | This person's INR share |
| share_value | DECIMAL NULL | For share-type splits (e.g. 2 = double share) |
| percentage | DECIMAL NULL | For percentage-type splits |

#### `Settlement`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| group_id | FK → Group | |
| from_user_id | FK → User | Who paid |
| to_user_id | FK → User | Who received |
| amount | DECIMAL(12,2) | |
| currency | CHAR(3) | |
| settlement_date | DATE | |
| notes | TEXT | |
| import_row_number | INT NULL | |
| created_at | TIMESTAMPTZ | |

#### `ImportReport`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| group_id | FK → Group | |
| filename | VARCHAR | Original filename |
| imported_count | INT | Rows successfully imported |
| skipped_count | INT | Rows skipped |
| created_at | TIMESTAMPTZ | |

#### `ImportAnomaly`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| report_id | FK → ImportReport | |
| row_number | INT | 1-indexed, includes header |
| category | VARCHAR | See list below |
| severity | VARCHAR | info / warning / error |
| description | TEXT | Human-readable message |
| original_value | TEXT NULL | Before correction |
| corrected_value | TEXT NULL | After correction |
| action_taken | VARCHAR | auto_corrected / skipped / flagged / reclassified |
| status | VARCHAR | auto_resolved / needs_review / user_approved / user_rejected |

---

## Part 2: All 20 Detected Anomalies

The importer ran on `expenses_export.csv` (42 rows) and detected **20 anomalies** (assignment required ≥ 12).

### Legend
- **auto_resolved** — safe to apply silently, no user decision needed
- **needs_review** — importer flags it; user must approve or reject before it affects balances
- **reclassified** — the row's semantic meaning changed (expense → settlement)

---

| # | Row | Category | Severity | Policy | Status |
|---|-----|----------|----------|--------|--------|
| 1 | 6 | `duplicate` | warning | Exact duplicate of row 5 (same date, amount, "Dinner at Marina Bites"). **SKIP** row 6. A silent keep would double-count ₹3,200. | auto_resolved → skipped |
| 2 | 9 | `name_normalized` | info | Payer field = `priya` (lowercase). Normalized to `Priya`. Case-insensitive match against NAME_ALIASES. | auto_resolved |
| 3 | 10 | `fractional_precision` | info | Amount `899.995` has 3 decimal places. Indian sub-paisa amounts are non-representable. Rounded to `900.00` (half-up). | auto_resolved |
| 4 | 11 | `name_normalized` | info | Payer field = `Priya S` (surname initial). Normalized to `Priya` via NAME_ALIASES. | auto_resolved |
| 5 | 13 | `missing_payer` | error | `paid_by` is empty for "Internet bill Jan". Cannot compute who is owed money without a payer. **Flag for manual review** — the user must assign a payer before this row can be imported. A silent guess (e.g., "assume Rohan") would be wrong. | needs_review |
| 6 | 14 | `settlement_as_expense` | warning | Description = "Rohan paid Aisha back". Note = "settlement". No `split_type` provided. This is a transfer, not a shared expense. **Reclassify as settlement** so it reduces Rohan's debt rather than creating a new split. | needs_review → reclassified |
| 7 | 15 | `percentage_sum_mismatch` | warning | Split percentages sum to 110% (30+30+30+20). Policy: **normalize proportionally** (each % ÷ 110 × 100), then flag as needs_review because the original intent may have been different. Silent normalization without surfacing is unacceptable. | needs_review |
| 8 | 23 | `name_normalized` | info | split_with contains `Dev's friend Kabir`. Resolved via NAME_ALIASES to `Kabir`. Kabir has a single-day timeline (Mar 11 only) per MEMBER_TIMELINE — he is a guest, not a flatmate. | auto_resolved |
| 9 | 24 | `conflicting_duplicate` | warning | Rows 24 and 25 both record "Thalassa dinner" on Mar 11, but with different amounts (₹2,360 vs ₹2,450). Row 25 note: "Aisha also logged this I think hers is wrong." **Tie-break rule**: later entry with corrective note overrides the earlier. Row 24 → skipped. Row 25 → kept. | auto_resolved → skipped (row 24) |
| 10 | 25 | `conflicting_duplicate` | warning | See row 24 above. Row 25 is the winner per the tie-break rule. | needs_review (kept) |
| 11 | 26 | `negative_amount` | info | Amount = `-30` USD. **Policy: negative = refund**, not an error. Stored as `amount=30, is_refund=True`. Split engine applies the refund as a negative share, crediting each participant. A deletion would erase the economic event. | auto_resolved |
| 12 | 27 | `wrong_year` | warning | Date = `3/1/2014`. Year 2014 is outside expected range 2025–2027. Row is in the Goa trip block (March 8–12 context). **Auto-correct to 2026-03-12** (last day of Goa trip). Flag for transparency. | needs_review |
| 13 | 27 | `name_normalized` | info | Payer = `rohan ` (trailing space). Normalized to `Rohan`. | auto_resolved |
| 14 | 28 | `missing_currency` | warning | `currency` column is empty for "Groceries DMart". **Default to INR** — all domestic grocery expenses in this dataset are INR. Logged so user can override if needed. | auto_resolved |
| 15 | 31 | `zero_amount` | warning | Amount = 0 for "Dinner order Swiggy". Note: "counted twice, ignore". **SKIP** — a zero expense contributes nothing to balances and the note confirms it was intentional. | auto_resolved → skipped |
| 16 | 32 | `percentage_sum_mismatch` | warning | Second occurrence: percentages sum to 110%. Same policy as row 15. Normalize + needs_review. | needs_review |
| 17 | 34 | `ambiguous_date` | warning | Date `5/4/2026` is ambiguous: **May 4** (MM/DD) or **April 5** (DD/MM). The rest of the CSV uses MM/DD format consistently. Interpret as May 4, but flag needs_review because a wrong date would misattribute Sam's membership window. | needs_review |
| 18 | 36 | `departed_member` | warning | "Groceries BigBasket" dated Apr 2. split_with includes `Meera`, who left Mar 31. **Remove Meera from the split** and redistribute her share among active members. Charging a departed member post-exit is incorrect. | needs_review |
| 19 | 38 | `settlement_as_expense` | warning | Description = "Sam deposit share". Note = "settlement". **Reclassify as settlement** — same policy as row 14. | needs_review → reclassified |
| 20 | 42 | `conflicting_split_type` | info | split_type = "equal" but split_details are provided with equal share values. No conflict in outcome — using equal split. Flagged for transparency so user knows split_details were provided but not needed. | auto_resolved |

---

## Part 3: Data Policies Summary

| Question the data forces | Policy chosen |
|--------------------------|---------------|
| Is a negative amount an error or a refund? | **Refund** — stored as positive with `is_refund=True`; credits participants |
| Two people logged the same dinner with different amounts — which row wins? | **Later entry with corrective note** wins (rows 24/25); both flagged |
| Does someone who moved out still owe post-exit expenses? | **No** — temporal membership enforced; departed members removed from splits |
| What if the payer name is missing? | **Flag as needs_review** — not imported until user assigns a payer |
| What if percentages don't sum to 100%? | **Normalize proportionally** — then flag; not silently applied |
| What if currency is missing? | **Default INR** — logged as anomaly, user can review |
| What if a settlement is recorded as an expense? | **Reclassify** as a settlement record, not an expense |
| What about Priya's complaint "a dollar is a rupee"? | **Convert USD at ₹95/USD** static rate — see DECISIONS.md |
| What about Sam's complaint about March electricity? | **Temporal filter**: Sam joined Apr 8, so all pre-Apr-8 expenses exclude him |
