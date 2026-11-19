from budget.analyze import pivot_on_account
import pandas as pd

from budget.balances_db import (
    get_balance_history,
    import_balance_history,
    insert_balance_snapshots,
)


def test_empty_database_has_expected_columns(tmp_path):
    history = get_balance_history(db_path=tmp_path / "balances.sqlite")

    assert history.empty
    assert list(history.columns) == ["Date", "Account", "Amount"]


def test_insert_is_idempotent_per_account_and_date(tmp_path):
    db_path = tmp_path / "balances.sqlite"
    insert_balance_snapshots(
        [{"name": "Checking", "balance": "12.50"}],
        "2026-01-02",
        db_path=db_path,
    )
    insert_balance_snapshots(
        [{"Account": "Checking", "Amount": 15}],
        "2026-01-02",
        db_path=db_path,
    )

    history = get_balance_history(db_path=db_path)
    assert len(history) == 1
    assert history.iloc[0].to_dict() == {
        "Date": "2026-01-02",
        "Account": "Checking",
        "Amount": 15.0,
    }


def test_history_is_date_ordered_and_works_with_account_pivot(tmp_path):
    db_path = tmp_path / "balances.sqlite"
    insert_balance_snapshots(
        [
            {"Account": "Checking", "Amount": 20, "Date": "2026-02-01"},
            {"Account": "Savings", "Amount": 30, "Date": "2026-01-01"},
            {"Account": "Checking", "Amount": 10, "Date": "2026-01-01"},
        ],
        db_path=db_path,
    )

    history = get_balance_history(db_path=db_path)
    assert list(history.columns) == ["Date", "Account", "Amount"]
    assert history["Date"].tolist() == ["2026-01-01", "2026-01-01", "2026-02-01"]
    pivot = pivot_on_account(history)
    assert pivot.loc["2026-01-01", "Checking"] == 10
    assert pivot.loc["2026-02-01", "Checking"] == 20


def test_import_sheet_history_skips_incomplete_rows_and_last_duplicate_wins(tmp_path):
    db_path = tmp_path / "balances.sqlite"
    balances = pd.DataFrame(
        [
            {
                "Date": "1/2/2026",
                "Account": "Checking",
                "Amount": 10,
                "Notes / Usage": "",
            },
            {
                "Date": "1/2/2026",
                "Account": "Checking",
                "Amount": 15,
                "Notes / Usage": "updated",
            },
            {"Date": "1/2/2026", "Account": "Savings", "Amount": None},
            {"Date": "", "Account": "Checking", "Amount": 30},
            {"Date": "not a date", "Account": "Checking", "Amount": 30},
        ]
    )

    assert import_balance_history(balances, db_path=db_path) == (2, 3)
    # Reimporting is safe and retains the final sheet row for the duplicate.
    assert import_balance_history(balances, db_path=db_path) == (2, 3)
    history = get_balance_history(db_path=db_path)
    assert history.to_dict("records") == [
        {"Date": "2026-01-02", "Account": "Checking", "Amount": 15.0}
    ]

    pivot = pivot_on_account(history)
    assert pivot.loc["2026-01-02", "Checking"] == 15
