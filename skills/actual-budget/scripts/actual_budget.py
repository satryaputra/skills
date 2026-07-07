#!/usr/bin/env python3
"""Actual Budget HTTP API helper.

Stdlib-only (Python 3.10+). Handles:

  * loading configuration from environment variables
  * caching accounts and categories to local JSON files (these change rarely)
  * HTTP requests with the x-api-key header (and optional encryption password)
  * converting amounts from the user's major currency unit (e.g. 120.30 USD or
    50000 IDR) to the integer Actual Budget expects (value * 100)

stdout is always JSON so an agent can parse it reliably. Errors go to stderr.
Exit code 0 on success, 1 on error.

Environment variables:
  ACTUAL_BUDGET_BASE_URL   e.g. https://actual.example.com/v1
  ACTUAL_BUDGET_API_KEY    the x-api-key value
  ACTUAL_BUDGET_SYNC_ID    budget sync id (Settings -> Show advanced -> Sync ID)
  ACTUAL_BUDGET_ENCRYPTION_PASSWORD   optional, only needed once for E2E budgets

Cache location: ~/.actual-budget-cache/{accounts,categories}.json
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CACHE_DIR = Path(os.path.expanduser("~/.actual-budget-cache"))
ACCOUNTS_CACHE = CACHE_DIR / "accounts.json"
CATEGORIES_CACHE = CACHE_DIR / "categories.json"


# --------------------------------------------------------------------------- #
# Config & helpers
# --------------------------------------------------------------------------- #
def config():
    base = os.environ.get("ACTUAL_BUDGET_BASE_URL", "").strip().rstrip("/")
    key = os.environ.get("ACTUAL_BUDGET_API_KEY", "").strip()
    sync = os.environ.get("ACTUAL_BUDGET_SYNC_ID", "").strip()
    enc = os.environ.get("ACTUAL_BUDGET_ENCRYPTION_PASSWORD", "").strip()
    missing = []
    if not base:
        missing.append("ACTUAL_BUDGET_BASE_URL")
    if not key:
        missing.append("ACTUAL_BUDGET_API_KEY")
    if not sync:
        missing.append("ACTUAL_BUDGET_SYNC_ID")
    if missing:
        die(f"Missing environment variables: {', '.join(missing)}")
    return base, key, sync, enc


def out(payload):
    """Emit a JSON result to stdout."""
    print(json.dumps(payload, ensure_ascii=False))


def die(msg, code=1):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def to_cents(value):
    """Convert a major-unit amount (e.g. 120.30 or 50000) to the integer
    Actual Budget wants (value * 100). Negative means an expense."""
    d = Decimal(str(value)) * Decimal(100)
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def http(method, url, body=None, key=None, enc=None):
    headers = {
        "x-api-key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Some Actual Budget servers sit behind Cloudflare, which bans the
        # default Python-urllib UA (HTTP 1010). A browser-like UA avoids that;
        # override with ACTUAL_BUDGET_USER_AGENT if a custom value is needed.
        "User-Agent": os.environ.get("ACTUAL_BUDGET_USER_AGENT", "Mozilla/5.0 (compatible; ActualBudgetSkill/1.0)"),
    }
    if enc:
        headers["budget-encryption-password"] = enc
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"_raw": raw}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            err = json.loads(err).get("error", err)
        except Exception:
            pass
        die(f"HTTP {e.code}: {err}")
    except Exception as e:  # noqa: BLE001
        die(f"Request failed: {e}")


def url_for(base, sync, *parts):
    return f"{base}/budgets/{sync}/" + "/".join(parts)


def write_cache(path, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"cached_at": datetime.now().isoformat(), "data": data}, ensure_ascii=False, indent=2)
    )


def read_cache(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_info(args):
    base, key, sync, enc = config()
    out(
        {
            "ok": True,
            "base_url": base,
            "sync_id": sync,
            "encryption_enabled": bool(enc),
            "cache_dir": str(CACHE_DIR),
            "accounts_cache_exists": ACCOUNTS_CACHE.exists(),
            "categories_cache_exists": CATEGORIES_CACHE.exists(),
        }
    )


def cmd_accounts(args):
    base, key, sync, enc = config()
    if not args.refresh and ACCOUNTS_CACHE.exists():
        cached = read_cache(ACCOUNTS_CACHE)
        if cached and cached.get("data") is not None:
            out({"ok": True, "data": cached["data"], "source": "cache", "cached_at": cached.get("cached_at")})
            return
    res = http("GET", url_for(base, sync, "accounts"), key=key, enc=enc)
    accounts = res.get("data", [])
    write_cache(ACCOUNTS_CACHE, accounts)
    out({"ok": True, "data": accounts, "source": "fetched"})


def cmd_categories(args):
    base, key, sync, enc = config()
    if not args.refresh and CATEGORIES_CACHE.exists():
        cached = read_cache(CATEGORIES_CACHE)
        if cached and cached.get("data") is not None:
            out({"ok": True, "data": cached["data"], "source": "cache", "cached_at": cached.get("cached_at")})
            return
    res = http("GET", url_for(base, sync, "categories"), key=key, enc=enc)
    cats = res.get("data", [])
    write_cache(CATEGORIES_CACHE, cats)
    out({"ok": True, "data": cats, "source": "fetched"})


def cmd_payees(args):
    base, key, sync, enc = config()
    res = http("GET", url_for(base, sync, "payees"), key=key, enc=enc)
    out({"ok": True, "data": res.get("data", [])})


def cmd_payee_create(args):
    base, key, sync, enc = config()
    body = {"payee": {"name": args.name}}
    res = http("POST", url_for(base, sync, "payees"), body=body, key=key, enc=enc)
    out({"ok": True, "data": res.get("data"), "message": f"payee created: {args.name}"})


def cmd_tx_list(args):
    base, key, sync, enc = config()
    url = url_for(base, sync, "accounts", args.account, "transactions")
    qs = []
    if args.since:
        qs.append(f"since_date={args.since}")
    if args.until:
        qs.append(f"until_date={args.until}")
    if args.limit is not None:
        qs.append(f"limit={args.limit}")
    if args.page is not None:
        qs.append(f"page={args.page}")
    if qs:
        url += "?" + "&".join(qs)
    res = http("GET", url, key=key, enc=enc)
    out({"ok": True, "data": res.get("data", [])})


def cmd_tx_create(args):
    base, key, sync, enc = config()
    tx = {"account": args.account, "date": args.date}
    if args.amount is not None:
        tx["amount"] = to_cents(args.amount)
    if args.payee:
        tx["payee"] = args.payee
    elif args.payee_name:
        tx["payee_name"] = args.payee_name
    if args.category:
        tx["category"] = args.category
    if args.notes is not None:
        tx["notes"] = args.notes
    if args.cleared is not None:
        tx["cleared"] = args.cleared == "true"
    if args.imported_payee:
        tx["imported_payee"] = args.imported_payee
    body = {
        "learnCategories": bool(args.learn_categories),
        "runTransfers": bool(args.run_transfers),
        "transaction": tx,
    }
    url = url_for(base, sync, "accounts", args.account, "transactions")
    res = http("POST", url, body=body, key=key, enc=enc)
    out(
        {
            "ok": True,
            "data": res.get("data") if isinstance(res, dict) else res,
            "message": res.get("message") if isinstance(res, dict) else "transaction created",
            "transaction": {k: v for k, v in tx.items() if k != "account"},
            "amount_cents": tx.get("amount"),
        }
    )


def cmd_tx_create_batch(args):
    base, key, sync, enc = config()
    payload = json.loads(Path(args.file).read_text())
    if isinstance(payload, list):
        transactions = payload
        learn = bool(args.learn_categories)
        run_t = bool(args.run_transfers)
    else:
        transactions = payload.get("transactions")
        learn = bool(payload.get("learn_categories", args.learn_categories))
        run_t = bool(payload.get("run_transfers", args.run_transfers))
        if transactions is None:
            die("--file must contain a 'transactions' array or be a JSON array")

    for t in transactions:
        if "amount_nominal" in t:
            t["amount"] = to_cents(t.pop("amount_nominal"))
        if "account" not in t:
            die("every transaction in the batch must include 'account'")

    body = {"learnCategories": learn, "runTransfers": run_t, "transactions": transactions}
    url = url_for(base, sync, "accounts", args.account, "transactions", "batch")
    res = http("POST", url, body=body, key=key, enc=enc)
    out(
        {
            "ok": True,
            "data": res.get("data") if isinstance(res, dict) else res,
            "message": res.get("message") if isinstance(res, dict) else f"{len(transactions)} transactions created",
            "count": len(transactions),
        }
    )


def cmd_tx_update(args):
    base, key, sync, enc = config()
    tx = {}
    if args.account:
        tx["account"] = args.account
    if args.date:
        tx["date"] = args.date
    if args.amount is not None:
        tx["amount"] = to_cents(args.amount)
    if args.payee is not None:
        tx["payee"] = args.payee
    if args.payee_name is not None:
        tx["payee_name"] = args.payee_name
    if args.category is not None:
        tx["category"] = args.category
    if args.notes is not None:
        tx["notes"] = args.notes
    if args.cleared is not None:
        tx["cleared"] = args.cleared == "true"
    if not tx:
        die("nothing to update; provide at least one field")
    body = {"transaction": tx}
    url = url_for(base, sync, "transactions", args.id)
    res = http("PATCH", url, body=body, key=key, enc=enc)
    out({"ok": True, "data": res.get("data") if isinstance(res, dict) else res,
         "message": res.get("message") if isinstance(res, dict) else "transaction updated"})


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        prog="actual_budget.py",
        description="Actual Budget HTTP API helper (stdout = JSON).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="show resolved config and cache status").set_defaults(func=cmd_info)

    a = sub.add_parser("accounts", help="list accounts (uses cache unless --refresh)")
    a.add_argument("--refresh", action="store_true", help="ignore cache and re-fetch")
    a.set_defaults(func=cmd_accounts)

    c = sub.add_parser("categories", help="list categories (uses cache unless --refresh)")
    c.add_argument("--refresh", action="store_true", help="ignore cache and re-fetch")
    c.set_defaults(func=cmd_categories)

    sub.add_parser("payees", help="list payees").set_defaults(func=cmd_payees)

    pyc = sub.add_parser("payee-create", help="create a single new payee")
    pyc.add_argument("--name", required=True)
    pyc.set_defaults(func=cmd_payee_create)

    tx = sub.add_parser("transactions", help="manage transactions")
    txn = tx.add_subparsers(dest="tx_action", required=True)

    tl = txn.add_parser("list", help="list transactions for an account")
    tl.add_argument("--account", required=True)
    tl.add_argument("--since")
    tl.add_argument("--until")
    tl.add_argument("--limit", type=int)
    tl.add_argument("--page", type=int)
    tl.set_defaults(func=cmd_tx_list)

    tc = txn.add_parser("create", help="create a single transaction")
    tc.add_argument("--account", required=True, help="destination account id")
    tc.add_argument("--date", required=True, help="YYYY-MM-DD")
    tc.add_argument("--amount", required=True, type=str,
                    help="signed value in major units, e.g. -50000 for a 50000 expense")
    tc.add_argument("--payee", help="existing payee id (preferred)")
    tc.add_argument("--payee-name", help="payee name to create on the fly (used only if no --payee)")
    tc.add_argument("--category", help="category id")
    tc.add_argument("--notes")
    tc.add_argument("--cleared", choices=["true", "false"], help="'true' or 'false'")
    tc.add_argument("--imported-payee")
    tc.add_argument("--learn-categories", action="store_true")
    tc.add_argument("--run-transfers", action="store_true")
    tc.set_defaults(func=cmd_tx_create)

    tcb = txn.add_parser("create-batch", help="create multiple transactions for ONE account")
    tcb.add_argument("--account", required=True, help="all transactions in the batch go to this account")
    tcb.add_argument("--file", required=True, help="JSON file: {transactions:[...]} or a bare array")
    tcb.add_argument("--learn-categories", action="store_true")
    tcb.add_argument("--run-transfers", action="store_true")
    tcb.set_defaults(func=cmd_tx_create_batch)

    tu = txn.add_parser("update", help="update an existing transaction")
    tu.add_argument("--id", required=True, help="transaction id")
    tu.add_argument("--account")
    tu.add_argument("--date")
    tu.add_argument("--amount", type=str)
    tu.add_argument("--payee")
    tu.add_argument("--payee-name")
    tu.add_argument("--category")
    tu.add_argument("--notes")
    tu.add_argument("--cleared", choices=["true", "false"])
    tu.set_defaults(func=cmd_tx_update)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        die(f"Unexpected error: {e}")