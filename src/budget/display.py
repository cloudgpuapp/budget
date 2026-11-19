import logging
import os

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)

_MISSING = "—"


def print_section(section_name: str, rows) -> None:
    try:
        from tabulate import tabulate
    except ImportError:
        raise ImportError("Missing dependency. Run:\n  pip install tabulate")

    if section_name == "summary":
        gross = rows.get("gross_income")
        net = rows.get("net_income")
        expenses = rows.get("total_expenses")
        disposable = rows.get("disposable")

        def fmt(v) -> str:
            return f"${v:,.2f}" if v is not None else _MISSING

        print(
            f"\n  SUMMARY"
            f"\n  Gross Income:    {fmt(gross)}"
            f"\n  Net Income:      {fmt(net)}"
            f"\n  Total Expenses:  {fmt(expenses)}"
            f"\n  Disposable:      {fmt(disposable)}"
        )
        return

    print(f"\n  {section_name.upper()}")

    logger.debug(f"{rows=}")
    table = [
        [row["label"], row["cell"], row["value"] if row["value"] is not None else ""]
        for row in rows
    ]

    print(
        tabulate(table, headers=["Label", "Cell", "Value"], tablefmt="rounded_outline")
    )


# TODO: Move all plotting to frontend and remove matplotlib dependency


def plot_accounts_on_ax(
    pivot: pd.DataFrame,
    columns: list[str],
    ax,
    title: str,
    start_date=None,
    end_date=None,
    show_total=True,
):
    if not columns:
        raise ValueError(f"No columns provided for {title}")

    if not pivot.index.is_monotonic_increasing:
        pivot = pivot.sort_index()

    # Apply date filtering
    if start_date is not None or end_date is not None:
        start_date = (
            pd.to_datetime(start_date) if start_date is not None else pivot.index.min()
        )
        end_date = (
            pd.to_datetime(end_date) if end_date is not None else pivot.index.max()
        )
        pivot = pivot.loc[start_date:end_date]

        if pivot.empty:
            raise ValueError(f"No data in date range for {title}")

    # Plot individual accounts
    for col in columns:
        ax.plot(pivot.index, pivot[col], label=col, linewidth=1, alpha=0.7)

    # Plot total (this is the important line)
    if show_total:
        total = pivot[columns].sum(axis=1)
        ax.plot(
            pivot.index,
            total,
            label="Total",
            linewidth=3,  # bold
        )

    ax.set_title(title)
    ax.grid(True)
    ax.legend()

    return ax


def configured_owners() -> list[str]:
    """Return owner prefixes configured in BUDGET_OWNERS, if any."""
    return [
        owner.strip()
        for owner in os.environ.get("BUDGET_OWNERS", "").split(",")
        if owner.strip()
    ]


def owner_from_account(account: str, owners: list[str] | None = None) -> str | None:
    """Find the configured owner prefix for an account, or None if unmatched."""
    owners = configured_owners() if owners is None else owners
    matches = [owner for owner in owners if account.startswith(owner)]
    return max(matches, key=len) if matches else None


def plot_split_accounts(
    pivot: pd.DataFrame,
    start_date=None,
    end_date=None,
):
    owners = configured_owners()
    if not owners:
        logger.info("Skipping owner plots; BUDGET_OWNERS is not configured")
        return

    owner_columns = {
        owner: [c for c in pivot.columns if owner_from_account(c, owners) == owner]
        for owner in owners
    }
    owners = [owner for owner in owners if owner_columns[owner]]
    if not owners:
        logger.info("Skipping owner plots; no accounts match BUDGET_OWNERS")
        return

    fig, axes = plt.subplots(len(owners), 1, figsize=(12, 4 * len(owners)), sharex=True)
    if len(owners) == 1:
        axes = [axes]

    for owner, ax in zip(owners, axes):
        plot_accounts_on_ax(
            pivot,
            owner_columns[owner],
            ax,
            f"{owner} Accounts",
            start_date=start_date,
            end_date=end_date,
        )

    axes[-1].set_xlabel("Date")

    plt.tight_layout()
    plt.show()


def plot_owner_accounts(pivot: pd.DataFrame, owner: str, **kwargs):
    owners = configured_owners()
    if not owners:
        logger.info("Skipping owner plot; BUDGET_OWNERS is not configured")
        return
    if owner not in owners:
        raise ValueError(f"Owner {owner!r} is not configured in BUDGET_OWNERS")

    cols = [c for c in pivot.columns if owner_from_account(c, owners) == owner]
    if not cols:
        logger.info("Skipping owner plot; no accounts match %r", owner)
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    plot_accounts_on_ax(pivot, cols, ax, f"{owner} Accounts", **kwargs)

    ax.set_xlabel("Date")
    plt.tight_layout()
    plt.show()
