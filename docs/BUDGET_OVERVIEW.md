# Budget Overview data source

## Current behavior

The home page (`GET /`) uses SQLite as its only data source. It groups rows in
the `transactions` table by the calendar month of `posted_date`, falling back
to `transacted_at` when no posted date is available. Rows with no usable date
and pending transactions are excluded. Positive amounts are counted as income;
negative amounts are counted as expenses by absolute value. The monthly
remaining amount is income minus expenses. Months link to `/transactions?month=YYYY-MM`. That parameter filters the spend
chart; it does not filter the transaction table.

These are transaction cash-flow totals. They are not the old manually entered
monthly budget values, do not include pending transactions, and do not imply
that all transactions have been categorized. The category editor and
categorization rules affect transaction classification, not these income and
expense totals.

## Change from Sheets

Previously, `/` called `load_all_months()`. That path read credentials and
spreadsheet settings, discovered matching tabs through the Google Sheets API,
fetched configured cell ranges, built monthly summaries, and stored the result
in the in-process budget cache. The overview displayed those configured
monthly figures and linked to the Sheets-backed month detail route.

The overview no longer calls `load_all_months()`, `build_trends()` or any
Sheets API function, and does not read `GOOGLE_SERVICE_ACCOUNT_KEY`,
`SPREADSHEET_ID`, `BUDGET_CONFIG`, or the Sheets cache. If SQLite cannot be
opened or queried, the page displays an error; it does not fall back to Sheets.
This prevents stale, unavailable, or differently defined spreadsheet values
from being presented as the current SQLite-backed overview.

## Preserved legacy paths

Sheets functionality remains in the repository for possible later use:

- `load_all_months()`, `_fetch_one()`, `build_trends()` and the Sheets imports
  in `app.py` remain for the legacy `GET /month/<sheet_name>` detail route.
- `templates/month.html` remains the rendering template for that route.
- `src/budget/sheets.py`, the Sheets-oriented CLI command, the cache module,
  and existing sheet configuration remain available to other workflows.
- The `/refresh` endpoint remains as a legacy redirect to `/balances`; it no
  longer refreshes or invalidates the overview's data.

These paths are deprecated for the Budget Overview. They are intentionally
retained rather than deleted. The overview itself has no links to the legacy
month route.

## Operational implications

The home page requires a working SQLite database containing transactions. Its
totals update from the database on each request and are not cached. A month
with no saved transactions will not appear. The optional spreadsheet settings
and Google credentials are still relevant to legacy routes and commands, but
are not prerequisites for rendering `/`.
