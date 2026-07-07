---
name: actual-budget
description: 'Record, list, or update transactions in Actual Budget. Triggers: "beli ...", "bayar ...", or any purchase/expense phrase.'
---

# Actual Budget

```bash
python scripts/actual_budget.py <command> [...args]
```

## Environment

| Variable                            | Required | Purpose                                                  |
| ----------------------------------- | -------- | -------------------------------------------------------- |
| `ACTUAL_BUDGET_BASE_URL`            | yes      | e.g. `https://actual.example.com/v1` (no trailing slash) |
| `ACTUAL_BUDGET_API_KEY`             | yes      | `x-api-key` value                                        |
| `ACTUAL_BUDGET_SYNC_ID`             | yes      | budget Sync ID                                           |
| `ACTUAL_BUDGET_ENCRYPTION_PASSWORD` | no       | only for E2E-encrypted budgets                           |

Verify with `python scripts/actual_budget.py info` - name any missing vars for the user.

## Amounts

Pass amounts in **major currency units** via `--amount`; the helper converts to
integer cents automatically. Expenses are negative, income positive.
Example: `--amount -50000` for a Rp 50 000 expense. Don't pre-multiply.

## Record a transaction

**Fuzzy-match**: case-insensitive partial match against the `name` field.

### 1. Account

The bank or wallet the money moves through. Cached at `~/.actual-budget-cache/accounts.json`.

```bash
python scripts/actual_budget.py accounts
```

Fuzzy-match the user's words against the account list.

**Done when:** exactly one account `id` is selected — or the user has been asked
to choose, listing available account names.

Force-refresh after a known new account: `python scripts/actual_budget.py accounts --refresh`.

### 2. Payee

Who the money goes to or comes from. Not cached — fetch fresh each session:

```bash
python scripts/actual_budget.py payees
```

Fuzzy-match (watch variants: "Shopeefood" vs "Shopee").

**Done when:** an existing payee `id` is reused via `--payee <id>`, or
`--payee-name "<name>"` is set for a genuinely new payee. Duplicates break
reports and rules — reuse first, create only when truly absent.

### 3. Category

Cached at `~/.actual-budget-cache/categories.json`.

```bash
python scripts/actual_budget.py categories
```

Fuzzy-match by meaning, not keywords ("bensin Pertamina" → Fuel/Transport;
"gaji" → an income category). Skip `hidden: true` categories.

**Done when:** a category `id` is set — or, when genuinely ambiguous (2–3
plausible fits), the user has chosen from a short numbered list.

Force-refresh: `python scripts/actual_budget.py categories --refresh`.

### 4. Post the transaction

```bash
python scripts/actual_budget.py transactions create \
  --account "<id>" --date "2025-07-01" --amount -50000 \
  --payee "<payee_id>" # OR --payee-name "Indomaret" if new
  --category "<category_id>" --notes "kopi" # notes optional
```

**Done when:** the helper returns a JSON object containing the new transaction's `id`.

### 5. Confirm

**Done when:** a one-line summary of the transaction is shown stating account, payee, category,
amount (with currency sign), and date. Example:

> Recorded Rp50.000 expense in _BCA_ to _Indomaret_, category _Food_, 2025-07-01.

## Other branches

When the user asks to **list**, **update**, or **batch-create** transactions
(not a single record), see [`references/commands.md`](references/commands.md).

## Reference

- [`references/api-reference.md`](references/api-reference.md) — endpoint summary, schemas, amount format.
- [`references/swagger.json`](references/swagger.json) — full OpenAPI spec; consult only if the above lacks what you need.
