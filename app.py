"""
app.py — Flask web interface for the budget reader.

Routes:
    SQLite pages: /, /transactions, /rules, /balances
    Legacy Google Sheets page: /month/<sheet_name>
    JSON endpoints: /api/transactions/spend, /api/balances/trend

Run:
    flask --app app run --debug
"""

import logging
import json
import os
import secrets
import sqlite3
import time
from urllib.parse import quote, unquote

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from budget.analyze import build_budget
from budget.balances_db import _connect, get_balance_history, get_transactions
from budget.categorizer import recategorize_all
from budget.config import ConfigError, get_env, load_toml
from budget.sheets import build_service, fetch_cells, list_sheet_names

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Legacy Sheets month-detail concurrency controls.
_MAX_WORKERS = max(1, int(os.environ.get("BUDGET_FETCH_WORKERS", 6)))
_RESULT_TIMEOUT = max(1, int(os.environ.get("BUDGET_RESULT_TIMEOUT", 20)))

app.jinja_env.filters["urlencode"] = quote

# ── Helpers ────────────────────────────────────────────────────────────────────


def _sort_key(sheet_name: str):
    """Sort 'M/YYYY' tab names chronologically."""
    try:
        parts = sheet_name.split("/")
        return (int(parts[1]), int(parts[0]))
    except (IndexError, ValueError):
        return (0, 0)


# The functions below are retained for the CLI and the legacy month-detail
# route. The Budget Overview route intentionally does not call them.
def _fetch_one(
    service,
    spreadsheet_id: str,
    sheet: str,
    all_refs: list[str],
    cells_config: dict,
    summary_config: dict,
) -> tuple[str, dict]:
    """Fetch and build budget for a single sheet. Designed for thread use."""
    logger.info(f"  Fetching '{sheet}'...")
    cell_values = fetch_cells(service, spreadsheet_id, sheet, all_refs)
    budget = build_budget(cells_config, cell_values, summary_config)
    return sheet, budget


def load_all_months() -> dict[str, dict]:
    """Legacy Sheets loader retained for month detail and other callers."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from budget.cache import budget_cache

    cached = budget_cache.get()
    if cached is not None:
        return cached

    key_file = get_env("GOOGLE_SERVICE_ACCOUNT_KEY")
    spreadsheet_id = get_env("SPREADSHEET_ID")
    config = load_toml()

    pattern = config.get("spreadsheet", {}).get("sheet_pattern")
    cells_config = config.get("cells", {})
    summary_config = config.get("summary", {})

    if not cells_config:
        raise ConfigError("No [cells.*] sections found in config.toml")

    all_refs = list(
        dict.fromkeys(
            ref for labels in cells_config.values() for ref in labels.values()
        )
    )

    service = build_service(key_file)
    sheet_names = list_sheet_names(service, spreadsheet_id, pattern=pattern)
    sheet_names.sort(key=_sort_key)

    logger.info(
        f"Discovered {len(sheet_names)} sheet(s), fetching with {_MAX_WORKERS} workers..."
    )

    result: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {}
        start_times = {}
        for sheet in sheet_names:
            start_times[sheet] = time.monotonic()
            futures[
                executor.submit(
                    _fetch_one,
                    service,
                    spreadsheet_id,
                    sheet,
                    all_refs,
                    cells_config,
                    summary_config,
                )
            ] = sheet

        for future in as_completed(futures, timeout=_RESULT_TIMEOUT * len(futures)):
            sheet = futures[future]
            elapsed = time.monotonic() - start_times[sheet]
            try:
                sheet_name, budget = future.result(timeout=_RESULT_TIMEOUT)
                result[sheet_name] = budget
                log_fn = logger.warning if elapsed > 5 else logger.info
                log_fn(f"Fetched sheet '{sheet}' in {elapsed:.2f}s")
            except Exception as e:
                logger.error(
                    f"Failed to fetch sheet '{sheet}' after {elapsed:.2f}s: {e}"
                )

    # Re-sort after parallel completion (arrival order is non-deterministic)
    result = dict(sorted(result.items(), key=lambda kv: _sort_key(kv[0])))

    budget_cache.set(result)
    return result


def build_trends(all_months: dict[str, dict]) -> dict:
    """Derive cross-month trend data from all loaded months."""
    months = list(all_months.keys())
    income = [all_months[m]["summary"].get("net_income") for m in months]
    expenses = [all_months[m]["summary"].get("total_expenses") for m in months]
    diff = [all_months[m]["summary"].get("disposable") for m in months]

    def _sum(vals):
        return sum(v for v in vals if v is not None)

    return {
        "months": months,
        "income": income,
        "expenses": expenses,
        "diff": diff,
        "total_income": _sum(income),
        "total_expenses": _sum(expenses),
        "avg_income": _sum(income) / len(months) if months else 0,
        "avg_expenses": _sum(expenses) / len(months) if months else 0,
    }


def load_sqlite_monthly_trends() -> dict:
    """Aggregate posted SQLite transactions into calendar-month totals."""
    connection = _connect()
    try:
        rows = connection.execute(
            """SELECT substr(COALESCE(posted_date, transacted_at), 1, 7) AS month,
                      SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
                      SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS expenses
               FROM transactions
               WHERE COALESCE(posted_date, transacted_at) IS NOT NULL
                 AND pending = 0
               GROUP BY month ORDER BY month"""
        ).fetchall()
    finally:
        connection.close()
    months = [row[0] for row in rows]
    income = [float(row[1] or 0) for row in rows]
    expenses = [float(row[2] or 0) for row in rows]
    return {
        "months": months,
        "income": income,
        "expenses": expenses,
        "diff": [i - e for i, e in zip(income, expenses)],
        "total_income": sum(income),
        "total_expenses": sum(expenses),
        "avg_income": sum(income) / len(months) if months else 0,
        "avg_expenses": sum(expenses) / len(months) if months else 0,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    error = trends = None
    try:
        trends = load_sqlite_monthly_trends()
    except Exception as e:
        logger.exception("Failed to load transaction summary from SQLite")
        error = str(e)

    return render_template(
        "index.html",
        trends=trends,
        error=error,
    )


@app.route("/month/<path:sheet_name>")
def month_detail(sheet_name: str):
    sheet_name = unquote(sheet_name)
    error = budget = all_months = None
    try:
        all_months = load_all_months()
        if sheet_name not in all_months:
            error = f"Sheet '{sheet_name}' not found."
        else:
            budget = all_months[sheet_name]
    except Exception as e:
        logger.exception("Failed to load budget")
        error = str(e)

    months = list(all_months.keys()) if all_months else []
    return render_template(
        "month.html",
        sheet_name=sheet_name,
        budget=budget,
        months=months,
        error=error,
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    # Balance pages read SQLite directly; rendering the destination reloads it.
    return redirect(url_for("balances"))


@app.route("/balances")
def balances():
    """Show current per-account balances and the SQLite net worth history."""
    source_filter = request.args.get("source", "all").lower()
    if source_filter not in {"all", "manual", "simplefin"}:
        source_filter = "all"
    error = None
    accounts = []
    net_worth = None
    latest_date = None
    try:
        history = get_balance_history()
        if "Source" in history.columns and source_filter != "all":
            history = history[history["Source"] == source_filter]
        if not history.empty:
            history["Date"] = history["Date"].astype(str)
            latest_date = history["Date"].max()

            for account, rows in history.groupby("Account", sort=True):
                latest = rows.sort_values("Date").iloc[-1]
                accounts.append(
                    {
                        "name": account,
                        "amount": float(latest["Amount"]),
                        "date": latest["Date"],
                        "stale": latest["Date"] != latest_date,
                    }
                )

            net_worth = sum(account["amount"] for account in accounts)
    except Exception as e:
        logger.exception("Failed to load balances from SQLite")
        error = str(e)

    return render_template(
        "balances.html",
        accounts=accounts,
        net_worth=net_worth,
        latest_date=latest_date,
        source_filter=source_filter,
        error=error,
    )


@app.get("/api/balances/trend")
def balances_trend():
    source_filter = request.args.get("source", "all").lower()
    if source_filter not in {"all", "manual", "simplefin"}:
        source_filter = "all"
    history = get_balance_history()
    if "Source" in history.columns and source_filter != "all":
        history = history[history["Source"] == source_filter]
    points = []
    if not history.empty:
        history["Date"] = history["Date"].astype(str)
        account_histories = {
            account: rows.sort_values("Date")
            for account, rows in history.groupby("Account", sort=True)
        }
        for day in sorted(history["Date"].unique()):
            amount = sum(
                float(available.iloc[-1]["Amount"])
                for rows in account_histories.values()
                if not (available := rows[rows["Date"] <= day]).empty
            )
            points.append({"date": day, "amount": amount})
    return jsonify(points)


@app.route("/rules", methods=["GET"])
def rules():
    connection = _connect()
    try:
        categories = connection.execute(
            "SELECT id, name FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
        rule_rows = connection.execute(
            """SELECT r.id, r.name, r.category_id, c.name, r.priority, r.is_active, r.conditions
               FROM categorization_rules r JOIN categories c ON c.id=r.category_id
               ORDER BY r.priority, r.id"""
        ).fetchall()
    finally:
        connection.close()
    rules_data = []
    for row in rule_rows:
        try:
            conditions = json.loads(row[6])
            match_value = conditions.get("rules", [{}])[0].get("value", "")
        except (json.JSONDecodeError, AttributeError, IndexError):
            match_value = ""
        rules_data.append(
            {
                "id": row[0],
                "name": row[1],
                "category_id": row[2],
                "category": row[3],
                "priority": row[4],
                "active": row[5],
                "match_value": match_value,
            }
        )
    return render_template(
        "rules.html",
        categories=categories,
        rules=rules_data,
        description=request.args.get("description", ""),
        selected_category=request.args.get("category_id", ""),
    )


@app.post("/categories")
def create_category():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Enter a category name.", "error")
    else:
        connection = _connect()
        try:
            connection.execute("INSERT INTO categories(name) VALUES (?)", (name,))
            connection.commit()
            flash(f"Added category {name}.", "success")
        except sqlite3.IntegrityError:
            connection.rollback()
            flash(f"Category {name} already exists.", "error")
        finally:
            connection.close()
    return redirect(url_for("rules"))


@app.post("/categories/<int:category_id>/rename")
def rename_category(category_id):
    name = request.form.get("name", "").strip()
    connection = _connect()
    try:
        if not name:
            flash("Enter a category name.", "error")
        else:
            connection.execute(
                "UPDATE categories SET name=? WHERE id=?", (name, category_id)
            )
            connection.commit()
            flash(
                "Category renamed."
                if connection.total_changes
                else "Category not found.",
                "success",
            )
    except sqlite3.IntegrityError:
        connection.rollback()
        flash(f"Category {name} already exists.", "error")
    finally:
        connection.close()
    return redirect(url_for("rules"))


@app.post("/categories/<int:category_id>/delete")
def delete_category(category_id):
    connection = _connect()
    try:
        referenced = connection.execute(
            "SELECT 1 FROM transactions WHERE category_id=? LIMIT 1", (category_id,)
        ).fetchone()
        if referenced:
            flash("Category is in use by a transaction.", "error")
            return redirect(url_for("rules"))
        connection.execute("DELETE FROM categories WHERE id=?", (category_id,))
        connection.commit()
        flash(
            "Category deleted." if connection.total_changes else "Category not found.",
            "success",
        )
    except sqlite3.IntegrityError:
        connection.rollback()
        flash("Category is in use by a rule or transaction.", "error")
    finally:
        connection.close()
    return redirect(url_for("rules"))


def _save_rule(rule_id=None):
    category_raw = request.form.get("category_id", "")
    value = request.form.get("value", "").strip()
    try:
        category_id = int(category_raw)
        priority = int(request.form.get("priority", "0"))
    except ValueError:
        category_id, priority = 0, 0
    connection = _connect()
    try:
        if (
            not value
            or not connection.execute(
                "SELECT 1 FROM categories WHERE id=?", (category_id,)
            ).fetchone()
        ):
            flash("Choose a category and enter a match value.", "error")
        else:
            conditions = json.dumps(
                {
                    "match_type": "ALL",
                    "rules": [
                        {"field": "description", "operator": "contains", "value": value}
                    ],
                }
            )
            if rule_id is None:
                connection.execute(
                    "INSERT INTO categorization_rules(name, category_id, priority, conditions) VALUES (?, ?, ?, ?)",
                    (
                        request.form.get("name", "").strip() or None,
                        category_id,
                        priority,
                        conditions,
                    ),
                )
            else:
                connection.execute(
                    "UPDATE categorization_rules SET name=?, category_id=?, priority=?, is_active=?, conditions=? WHERE id=?",
                    (
                        request.form.get("name", "").strip() or None,
                        category_id,
                        priority,
                        int(request.form.get("is_active") == "1"),
                        conditions,
                        rule_id,
                    ),
                )
            recategorize_all(connection)
            connection.commit()
            flash("Rule saved.", "success")
    finally:
        connection.close()
    return redirect(url_for("rules"))


@app.post("/rules")
def create_rule():
    return _save_rule()


@app.post("/rules/<int:rule_id>/edit")
def edit_rule(rule_id):
    return _save_rule(rule_id)


@app.post("/rules/<int:rule_id>/delete")
def delete_rule(rule_id):
    connection = _connect()
    try:
        connection.execute("DELETE FROM categorization_rules WHERE id=?", (rule_id,))
        recategorize_all(connection)
        connection.commit()
    finally:
        connection.close()
    return redirect(url_for("rules"))


@app.post("/rules/run")
def run_rules():
    connection = _connect()
    try:
        count = recategorize_all(connection)
        connection.commit()
    finally:
        connection.close()
    flash(f"Updated {count} transaction(s).", "success")
    return redirect(url_for("rules"))


@app.route("/transactions")
def transactions():
    per_page = 50
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    account_id = request.args.get("account_id", "").strip()
    category_id = request.args.get("category_id", "").strip()
    pending = request.args.get("pending", "").strip()
    query = request.args.get("q", "").strip()
    spend_category_ids = [
        value.strip()
        for value in request.args.getlist("spend_category_id")
        if value.strip()
    ]
    selected_month = request.args.get("month", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    clauses, values = [], []
    if account_id:
        clauses.append("t.account_id = ?")
        values.append(account_id)
    if category_id == "uncategorized":
        clauses.append("t.category_id IS NULL")
    elif category_id:
        try:
            values.append(int(category_id))
            clauses.append("t.category_id = ?")
        except ValueError:
            category_id = ""
    if pending in ("0", "1"):
        clauses.append("t.pending = ?")
        values.append(int(pending))
    else:
        pending = ""
    if query:
        clauses.append("INSTR(LOWER(t.description), LOWER(?)) > 0")
        values.append(query)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    connection = _connect()
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM transactions t" + where, values
        ).fetchone()[0]
        rows = connection.execute(
            """SELECT t.account_id, t.transaction_id, COALESCE(t.posted_date, t.transacted_at),
                      a.name, t.description, t.pending, t.amount, t.category_id, c.name,
                      t.is_manual_category
               FROM transactions t JOIN accounts a ON a.id=t.account_id
               LEFT JOIN categories c ON c.id=t.category_id"""
            + where
            + " ORDER BY COALESCE(t.posted_date, t.transacted_at) DESC, t.rowid DESC LIMIT ? OFFSET ?",
            [*values, per_page, (page - 1) * per_page],
        ).fetchall()
        accounts = connection.execute(
            "SELECT id, name FROM accounts ORDER BY name COLLATE NOCASE"
        ).fetchall()
        categories = connection.execute(
            "SELECT id, name FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
        months = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT substr(COALESCE(posted_date, transacted_at), 1, 7) "
                "FROM transactions WHERE COALESCE(posted_date, transacted_at) IS NOT NULL "
                "ORDER BY 1 DESC"
            ).fetchall()
        ]
        # A date range takes precedence when either date is supplied.
        date_clauses = []
        date_values = []
        has_date_range = bool(start_date or end_date)
        if start_date:
            date_clauses.append("COALESCE(t.posted_date, t.transacted_at) >= ?")
            date_values.append(start_date)
        if end_date:
            date_clauses.append("COALESCE(t.posted_date, t.transacted_at) <= ?")
            date_values.append(end_date)
        elif selected_month and not has_date_range:
            date_clauses.append(
                "substr(COALESCE(t.posted_date, t.transacted_at), 1, 7) = ?"
            )
            date_values.append(selected_month)
        if has_date_range:
            selected_month = ""
        chart_category_clauses = []
        chart_category_values = []
        chart_category_ids = []
        for value in spend_category_ids:
            if value == "uncategorized":
                continue
            try:
                chart_category_ids.append(int(value))
            except ValueError:
                continue
        if "uncategorized" in spend_category_ids:
            chart_category_clauses.append("t.category_id IS NULL")
        if chart_category_ids:
            chart_category_clauses.append(
                "t.category_id IN (" + ",".join("?" for _ in chart_category_ids) + ")"
            )
            chart_category_values.extend(chart_category_ids)
        chart_filter_sql = (
            " AND (" + " OR ".join(chart_category_clauses) + ")"
            if chart_category_clauses
            else ""
        )
        spend_rows = connection.execute(
            "SELECT COALESCE(c.name, 'Uncategorized'), SUM(-t.amount) "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.amount < 0"
            + ((" AND " + " AND ".join(date_clauses)) if date_clauses else "")
            + chart_filter_sql
            + " GROUP BY t.category_id, c.name ORDER BY 1 COLLATE NOCASE",
            [*date_values, *chart_category_values],
        ).fetchall()
    finally:
        connection.close()
    transactions_data = [
        dict(
            zip(
                (
                    "account_id",
                    "transaction_id",
                    "date",
                    "account",
                    "description",
                    "pending",
                    "amount",
                    "category_id",
                    "category",
                    "manual",
                ),
                row,
            )
        )
        for row in rows
    ]
    filters = {
        "account_id": account_id,
        "category_id": category_id,
        "pending": pending,
        "q": query,
        "month": selected_month,
        "start_date": start_date,
        "end_date": end_date,
        "spend_category_id": spend_category_ids,
    }
    spend_total = sum(amount for _, amount in spend_rows)
    palette = [
        "#4778a8",
        "#e08b45",
        "#65a36e",
        "#b65d5d",
        "#8a70ad",
        "#c5a537",
        "#4b9b9a",
        "#ce719b",
        "#7d8791",
        "#9b704d",
    ]
    spend_breakdown = []
    for index, (name, amount) in enumerate(spend_rows):
        percent = amount / spend_total * 100 if spend_total else 0
        color = palette[index % len(palette)]
        spend_breakdown.append(
            {"name": name, "amount": amount, "percent": percent, "color": color}
        )
    return render_template(
        "transactions.html",
        transactions=transactions_data,
        accounts=accounts,
        categories=categories,
        filters=filters,
        page=page,
        pages=max(1, (total + per_page - 1) // per_page),
        total=total,
        months=months,
        selected_month=selected_month,
        start_date=start_date,
        end_date=end_date,
        spend_breakdown=spend_breakdown,
        spend_total=spend_total,
    )


@app.get("/api/transactions/spend")
def transaction_spend():
    month = request.args.get("month", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    clauses, values = [], []
    if start_date:
        clauses.append("COALESCE(t.posted_date, t.transacted_at) >= ?")
        values.append(start_date)
    if end_date:
        clauses.append("COALESCE(t.posted_date, t.transacted_at) <= ?")
        values.append(end_date)
    elif month and not (start_date or end_date):
        clauses.append("substr(COALESCE(t.posted_date, t.transacted_at), 1, 7) = ?")
        values.append(month)
    selected = request.args.getlist("spend_category_id")
    category_ids = []
    category_clauses = []
    for value in selected:
        if value == "uncategorized":
            category_clauses.append("t.category_id IS NULL")
        else:
            try:
                category_ids.append(int(value))
            except ValueError:
                continue
    if category_ids:
        category_clauses.append("t.category_id IN (" + ",".join("?" for _ in category_ids) + ")")
        values.extend(category_ids)
    if category_clauses:
        clauses.append("(" + " OR ".join(category_clauses) + ")")
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT COALESCE(c.name, 'Uncategorized'), SUM(-t.amount) "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.amount < 0" + (" AND " + " AND ".join(clauses) if clauses else "") +
            " GROUP BY t.category_id, c.name ORDER BY 1 COLLATE NOCASE", values
        ).fetchall()
    finally:
        connection.close()
    palette = ["#4778a8", "#e08b45", "#65a36e", "#b65d5d", "#8a70ad", "#c5a537", "#4b9b9a", "#ce719b", "#7d8791", "#9b704d"]
    total = sum(float(amount) for _, amount in rows)
    breakdown = [
        {"name": name, "amount": float(amount), "percent": float(amount) / total * 100 if total else 0, "color": palette[index % len(palette)]}
        for index, (name, amount) in enumerate(rows)
    ]
    return jsonify({"total": total, "breakdown": breakdown})


@app.post("/transactions/<account_id>/<transaction_id>/category")
def update_transaction_category(account_id, transaction_id):
    raw_category_id = request.form.get("category_id", "").strip()
    connection = _connect()
    try:
        exists = connection.execute(
            "SELECT description FROM transactions WHERE account_id=? AND transaction_id=?",
            (account_id, transaction_id),
        ).fetchone()
        if exists is None:
            if request.is_json or request.headers.get("X-Requested-With") == "fetch":
                return jsonify({"error": "Transaction not found."}), 404
            flash("Transaction not found.", "error")
        elif raw_category_id:
            try:
                category_id = int(raw_category_id)
            except ValueError:
                category_id = None
            if (
                category_id is None
                or not connection.execute(
                    "SELECT 1 FROM categories WHERE id=?", (category_id,)
                ).fetchone()
            ):
                if request.is_json or request.headers.get("X-Requested-With") == "fetch":
                    return jsonify({"error": "Choose a valid category."}), 400
                flash("Choose a valid category.", "error")
            else:
                connection.execute(
                    "UPDATE transactions SET category_id=?, is_manual_category=1, rule_id=NULL WHERE account_id=? AND transaction_id=?",
                    (category_id, account_id, transaction_id),
                )
        else:
            from budget.categorizer import categorize_transaction

            transaction = connection.execute(
                "SELECT description, category_id, rule_id FROM transactions WHERE account_id=? AND transaction_id=?",
                (account_id, transaction_id),
            ).fetchone()
            category_id, rule_id = categorize_transaction(
                connection,
                {
                    "description": transaction[0],
                    "category_id": None,
                    "rule_id": None,
                    "is_manual_category": 0,
                },
            )
            connection.execute(
                "UPDATE transactions SET category_id=?, rule_id=?, is_manual_category=0 WHERE account_id=? AND transaction_id=?",
                (category_id, rule_id, account_id, transaction_id),
            )
        connection.commit()
        updated = connection.execute(
            "SELECT t.category_id, c.name, t.is_manual_category FROM transactions t "
            "LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.account_id=? AND t.transaction_id=?",
            (account_id, transaction_id),
        ).fetchone()
    finally:
        connection.close()
    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"category_id": updated[0], "category": updated[1], "manual": bool(updated[2])})
    return_to = request.form.get("return_to", "")
    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = url_for("transactions")
    return redirect(return_to)


if __name__ == "__main__":
    app.run(debug=True)
