from budget.analyze import pivot_on_account
from budget.balances_db import get_balance_history, insert_balance_snapshots


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
