# AI_USAGE.md — AI Tool Usage Log

## Tool Used

**Antigravity** by Google DeepMind (IDE-integrated AI coding assistant).

Antigravity was used as the **primary development collaborator** throughout this project. It assisted with:
- Scaffolding Django models, serializers, and DRF views
- Writing the CSS design system
- Drafting the importer anomaly detection logic
- Suggesting the greedy debt simplification algorithm

---

## Key Prompts

1. *"Build a Django REST Framework backend for a shared expenses app. I need: JWT auth, group membership with join/leave dates, expenses with 4 split types (equal/unequal/percentage/share), settlements, and a balance engine."*

2. *"Write the CSV importer. The file has at least 12 deliberate data problems. For each problem the importer must: detect it, surface it to the user, and handle it per a policy I document. A crashed import and a silent guess are both wrong."*

3. *"Design a React UI that shows Rohan's full row-by-row ledger — every expense contributing to his balance, with a running total. No toy example, use the real data from the import."*

4. *"Implement debt simplification: Aisha wants one number per person. Who pays whom, how much, done. Produce the minimum number of transactions."*

5. *"Run the full CSV through the engine standalone (no Django/DB). Print every anomaly detected, then Rohan's complete ledger."*

---

## Three Cases Where the AI Was Wrong

### Case 1: `user_id` Read/Write Conflict in GroupMembershipSerializer

**What the AI generated**:
```python
class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)  # AI's original
    ...
```

**The problem**: Making `user_id` write-only means the frontend cannot read `m.user_id` from the API response. The GroupDetailPage referenced `m.user_id` and `m.user_name` as flat fields. This caused the entire members list to render blank — the serializer returned `null` for both fields.

**How I caught it**: Running the frontend showed empty member lists. Inspecting the API response in the browser showed `user_id` was absent from the JSON (write_only = excluded from output).

**What I changed**: Made `user_id` and `user_name` read-only source fields instead:
```python
user_id   = serializers.IntegerField(source='user.id', read_only=True)
user_name = serializers.CharField(source='user.name', read_only=True)
```
The POST to add members still works because it reads `user_id` directly from `request.data`, not from the serializer.

---

### Case 2: Settlement Creation Hardcoded `from_user = request.user`

**What the AI generated**:
```python
settlement = Settlement.objects.create(
    group=group,
    from_user=request.user,   # AI hardcoded this
    ...
)
```

**The problem**: In the flatmate scenario, any group member (e.g., Aisha logged in) should be able to record that *Rohan paid Priya*. If `from_user` is always the logged-in user, you can only record settlements where you yourself are the payer. The entire simplified-debt "Settle" button feature (which pre-fills a different person as payer) would silently ignore the user's selection.

**How I caught it**: Testing the "Settle" button on the Balances tab — clicking "Rohan → Aisha: ₹25,467" while logged in as Aisha created a settlement with `from_user=Aisha` (wrong). Rohan was not debited.

**What I changed**: Added `from_user_id` as an optional field in `SettlementCreateSerializer` and updated the view to use it when provided:
```python
from_user_id = data.get('from_user_id') or request.data.get('from_user_id')
if from_user_id:
    from_user = User.objects.get(id=int(from_user_id))
else:
    from_user = request.user
```

The same pattern was applied to expense creation (`paid_by_id`).

---

### Case 3: Importer's Conflicting Duplicate Detection Had No Date Guard

**What the AI generated** (initial version of `are_conflicting_duplicates`):
```python
def are_conflicting_duplicates(row1, row2):
    words1 = set(w for w in desc1.split() if len(w) > 2)
    words2 = set(w for w in desc2.split() if len(w) > 2)
    common = [w for w in words1 if w in words2]
    if len(common) >= 2 and row1['parsed_amount'] != amount2:
        return True  # No date check — any two rows with similar descriptions flagged!
```

**The problem**: "Groceries DMart" appears on rows 3, 17, 28, and 41 (four different months). Without a date guard, every pair of grocery rows was flagged as a conflicting duplicate — producing 6 false-positive anomalies. The import report was flooded with fake conflicts.

**How I caught it**: Running `python rohan_ledger.py` showed `conflicting_duplicate` anomalies for rows 3↔17, 3↔28, 3↔41, etc. — all legitimate grocery expenses on different dates. The description-only match was far too broad.

**What I changed**: Added a date proximity guard — only flag as conflicting if the two rows are within 1 day of each other:
```python
d1 = datetime.strptime(row1['parsed_date'], '%Y-%m-%d')
d2 = datetime.strptime(date2_iso, '%Y-%m-%d')
if abs((d1 - d2).days) > 1:
    return False   # Different days → not a conflict
```
This reduced false positives from 6 down to 0 while still correctly catching the real Thalassa conflict (rows 24/25, same day).

---

## Additional Observations

- The AI initially suggested `djangorestframework-simplejwt` for authentication. I chose to write a custom JWT implementation instead, because `simplejwt` adds a `TokenRefresh` and `TokenBlacklist` workflow that is heavier than needed for this scope. Understanding every line of the auth code was important for the live evaluation.

- The AI suggested using `heapq` for the debt simplification min-heap. The implementation is correct (I traced it manually for the 7-member case in `test_engine.py`), but I moved from `heapq` to a sorted-list approach in `balances.py` for readability, since readability matters more than performance for n ≤ 10.

- The AI consistently produced correct split-engine logic. I verified the equal, unequal, percentage, and share splits by hand for the values in `test_engine.py` before trusting the output.
