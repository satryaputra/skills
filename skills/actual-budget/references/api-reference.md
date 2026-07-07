# Actual Budget HTTP API — quick reference

Full OpenAPI spec: `swagger.json` (in this folder). This file is the curated,
worked summary for the operations this skill uses. Base path uses
`ACTUAL_BUDGET_BASE_URL` (without trailing slash) and the budget sync id from
`ACTUAL_BUDGET_SYNC_ID`.

Auth: `x-api-key` header = `ACTUAL_BUDGET_API_KEY`.
Optional `budget-encryption-password` header = `ACTUAL_BUDGET_ENCRYPTION_PASSWORD`
(only needed for the first call to an end-to-end encrypted budget).

## Amount format

Amounts are **integers** representing the value × the smallest unit. In
practice Actual Budget stores `value × 100` for every currency, so:

- USD `120.30` → `12030`
- IDR `50000` → `5000000`
- Expenses are **negative**, income is **positive**.

The helper script does this conversion for you when you pass `--amount` as a
major-unit value (e.g. `--amount -50000`). For batch payloads you may put
either `amount` (already cents) or `amount_nominal` (major units, auto-converted).

## Endpoints

All paths are relative to the server with `{budgetSyncId}` substituted.

### Accounts
`GET /budgets/{budgetSyncId}/accounts`
→ `{ "data": [ { "id", "name", "offbudget", "closed" } ] }`

### Categories
`GET /budgets/{budgetSyncId}/categories`
→ `{ "data": [ { "id", "name", "is_income", "hidden", "group_id" } ] }`

### Payees
`GET /budgets/{budgetSyncId}/payees`
→ `{ "data": [ { "id", "name", "category", "transfer_acct" } ] }`

`POST /budgets/{budgetSyncId}/payees`
body: `{ "payee": { "name": "Fidelity" } }`
→ `{ "data": "<new payee id>" }`

### Transactions
`GET /budgets/{budgetSyncId}/accounts/{accountId}/transactions`
query: `since_date` (YYYY-MM-DD), optional `until_date`, `page`, `limit`.
→ `{ "data": [ Transaction ] }`

`POST /budgets/{budgetSyncId}/accounts/{accountId}/transactions`
body:
```json
{
  "learnCategories": false,
  "runTransfers": false,
  "transaction": {
    "account": "<accountId>",
    "date": "2023-06-23",
    "amount": -7374,
    "payee": "<payee id>",
    "payee_name": "Remitly",
    "category": "<category id>",
    "notes": "...",
    "cleared": false
  }
}
```
Use `payee` (id) to attach an existing payee, or `payee_name` to create the
payee on the fly. Do not send both. Response: `{ "message": "ok" }`.

`POST /budgets/{budgetSyncId}/accounts/{accountId}/transactions/batch`
body: same shape but `transactions` (array) instead of `transaction`. All
transactions in a batch must belong to the **same** account (the one in the
URL path). Response: `{ "message": "ok" }`.

`PATCH /budgets/{budgetSyncId}/transactions/{transactionId}`
body: `{ "transaction": { ...fields to change... } }`. `account` and `date`
are required by the schema. Response: `{ "message": "Transaction updated" }`.

## Schemas (abbreviated)

- **Account**: `id`, `name`, `offbudget` (bool), `closed` (bool)
- **Category**: `id`, `name`, `is_income` (bool), `hidden` (bool), `group_id`
- **Payee**: `id`, `name`, `category` (default category, nullable), `transfer_acct`
- **Transaction**: `id`, `account`, `date`, `amount` (int, cents), `payee`,
  `payee_name` (create only), `imported_payee`, `category`, `notes`,
  `imported_id`, `transfer_id`, `cleared`, `subtransactions` (get/create only)

## Error responses
`400` invalid input, `404` resource not found, `500` server error — each with
`{ "error": "..." }`.