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
