# Commands Reference

Disclosed reference for branches beyond single-transaction creation.
Helper: `python scripts/actual_budget.py <command> [...args]` — stdout is JSON.

## List transactions

```bash
python scripts/actual_budget.py transactions list --account "<id>" \
  --since "2025-07-01" --until "2025-07-31"     # dates optional (YYYY-MM-DD)
  --limit 50 --page 1                            # pagination optional
```

Present results as a readable list: date, signed amount, payee name, category
name, notes. Resolve payee and category ids to names using the data you already
fetched — the user should see names, never raw ids.

## Update a transaction

Requires the transaction `id`. If the user doesn't have it, list the account's
transactions and find the match by date + amount + payee.

```bash
python scripts/actual_budget.py transactions update \
  --id "<tx_id>" --account "<id>"      # account required by the API
  --amount -60000 --category "<id>" --notes "updated" --cleared true   # any subset
```

Only fields you pass change. `account` is required by the schema — pass the
current value if it shouldn't move. If the API complains about `date`, add
`--date` with the current date.

## Batch create (multiple transactions, one account)

Write a JSON file with an array of transaction objects:

```json
{
  "transactions": [
    { "account": "<id>", "date": "2025-07-01", "amount_nominal": -50000, "payee_name": "Indomaret", "category": "<id>", "notes": "kopi" },
    { "account": "<id>", "date": "2025-07-01", "amount_nominal": -30000, "payee_name": "Tuku", "category": "<id>" }
  ]
}
```

`amount_nominal` is auto-converted to cents; `amount` is already cents — either
works. Every entry must include `account`.

```bash
python scripts/actual_budget.py transactions create-batch --account "<id>" --file /tmp/tx.json
```

All batch transactions must share **one** account (the one in the URL). If the
user gives transactions across different accounts, run one batch per account —
don't silently reassign.
