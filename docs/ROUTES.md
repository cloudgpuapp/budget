# Routes and API

| Method and path | Type | Behavior |
| --- | --- | --- |
| `GET /` | Page | SQLite monthly income, expense, and remaining totals. |
| `GET /transactions` | Page | Transaction table and spend chart. `month`, `start_date`, and `end_date` filter the chart; account, category, pending, and `q` filter the table. |
| `GET /rules` | Page | Category and categorization-rule editor. |
| `GET /balances` | Page | Latest per-account balances and net-worth history; optional `source=manual | simplefin`. |
| `GET /month/<sheet_name>` | Legacy page | Google Sheets month detail. Requires Sheets credentials and configuration. |
| `POST /refresh` | Legacy action | Redirects to `/balances`; no longer refreshes the overview. |
| `GET /api/balances/trend` | JSON | Balance history points, optionally filtered by `source`. |
| `GET /api/transactions/spend` | JSON | Spend total and category breakdown. Accepts `month`, date bounds, and repeated `spend_category_id` filters. |
| `POST /transactions/<account_id>/<transaction_id>/category` | Form action or JSON response | Submit form-encoded `category_id`; an empty value clears the override and reapplies rules. Requests marked as JSON or fetch receive a JSON response. |
| `POST /categories`, `/categories/<id>/rename`, `/categories/<id>/delete` | Form action | Create, rename, or delete categories. |
| `POST /rules`, `/rules/<id>/edit`, `/rules/<id>/delete`, `/rules/run` | Form action | Create, edit, delete, or rerun categorization rules. |

There is no authentication or CSRF protection. Do not expose the app directly to an untrusted network.
