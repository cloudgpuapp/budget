"""SQLite persistence for daily account balance snapshots."""

import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

logger = logging.getLogger(__name__)


def _database_path(db_path: str | os.PathLike[str] | None = None) -> str:
    if db_path is not None:
        return os.fspath(db_path)
    configured_path = os.environ.get("BUDGET_DB_PATH")
    if configured_path:
        return configured_path
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return os.fspath(data_home / "budget" / "balances.sqlite3")


def _connect(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    path = _database_path(db_path)
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        path = os.path.expanduser(path)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS balance_snapshots (
            account TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            PRIMARY KEY (account, date)
        )
    """)
    connection.execute("PRAGMA user_version = 1")
    return connection


def _as_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()


def insert_balance_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
    snapshot_date: date | datetime | str | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> None:
    """Insert or replace snapshots for a date.

    Each item must contain ``Account`` or ``name`` and ``Amount`` or ``balance``.
    If a record includes ``Date`` or ``date``, it takes precedence over the
    shared ``snapshot_date`` (which defaults to today).
    """
    default_date = _as_date(snapshot_date or date.today())
    rows = []
    for snapshot in snapshots:
        account = snapshot.get("Account", snapshot.get("name"))
        amount = snapshot.get("Amount", snapshot.get("balance"))
        row_date = snapshot.get("Date", snapshot.get("date", default_date))
        if account is None or amount is None:
            raise ValueError("Each snapshot must include an account and amount")
        rows.append((str(account), _as_date(row_date), float(amount)))

    connection = _connect(db_path)
    try:
        connection.executemany(
            """INSERT INTO balance_snapshots (account, date, amount)
               VALUES (?, ?, ?)
               ON CONFLICT(account, date) DO UPDATE SET amount = excluded.amount""",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def import_balance_history(
    balances: pd.DataFrame,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> tuple[int, int]:
    """Import sheet history, skipping incomplete or invalid rows.

    Returns the number of valid rows written and the number skipped. Repeated
    account/date pairs are processed in sheet order, so the final row wins.
    """
    rows = []
    skipped = 0
    for _, record in balances.iterrows():
        date_value = record.get("Date")
        account_value = record.get("Account")
        amount_value = record.get("Amount")
        is_blank = any(
            pd.isna(value) or not str(value).strip()
            for value in (date_value, account_value, amount_value)
        )
        if is_blank:
            skipped += 1
            continue

        parsed_date = pd.to_datetime(date_value, errors="coerce")
        try:
            amount = float(str(amount_value).replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            amount = float("nan")
        if pd.isna(parsed_date) or pd.isna(amount):
            skipped += 1
            continue
        rows.append(
            (str(account_value).strip(), parsed_date.date().isoformat(), amount)
        )

    connection = _connect(db_path)
    try:
        connection.executemany(
            """INSERT INTO balance_snapshots (account, date, amount)
               VALUES (?, ?, ?)
               ON CONFLICT(account, date) DO UPDATE SET amount = excluded.amount""",
            rows,
        )
        connection.commit()
    finally:
        connection.close()

    logger.info(
        "Imported %d balance row(s); skipped %d incomplete or invalid row(s).",
        len(rows),
        skipped,
    )
    return len(rows), skipped


def get_balance_history(
    *, db_path: str | os.PathLike[str] | None = None
) -> pd.DataFrame:
    """Return history as Date, Account, Amount columns, ordered by date."""
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            "SELECT date, account, amount FROM balance_snapshots ORDER BY date, account"
        ).fetchall()
    finally:
        connection.close()
    return pd.DataFrame(rows, columns=["Date", "Account", "Amount"])
