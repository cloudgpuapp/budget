# Budget

A personal budgeting tool that reads monthly values from Google Sheets. It includes a command line report, a Flask dashboard, and a retirement forecast.

## Requirements

- Python 3.11 or newer
- A Google spreadsheet containing budget tabs and, for retirement forecasting, a `Balances` tab
- A Google Cloud service account with the Google Sheets API enabled

The service account needs viewer access to the spreadsheet. The app uses the Sheets API in read-only mode.

## Installation

Clone the repository and create an isolated environment:

```sh
git clone <repository-url>
cd budget
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Create a Google Cloud service account, enable the Google Sheets API for its project, and download its JSON key. Keep the key outside the repository and do not commit it. Share your spreadsheet with the service account email address as a viewer.

Copy `sample_config.toml` to a location you control (for example `config.toml`) and edit the cell references to match your sheet layout. Set `spreadsheet.sheet_pattern` to a regular expression matching the monthly tab names you want to include; for example `"^\\d{1,2}/\\d{4}$"` matches tabs named `1/2026` or `12/2026`. If omitted, every tab in the spreadsheet is read. The `summary` table is optional and can map fields to configured rows or derive values from earlier summary fields; see the comments in the sample configuration and `src/budget/analyze.py`.

Create a `.env` file in the working directory (or export these variables in your shell):

```dotenv
GOOGLE_SERVICE_ACCOUNT_KEY=/absolute/path/to/service-account.json
SPREADSHEET_ID=your_google_spreadsheet_id
BUDGET_CONFIG=/absolute/path/to/config.toml
```

`SPREADSHEET_ID` is the ID in the spreadsheet URL between `/d/` and `/edit`. The CLI loads `.env` automatically. For the web app, run it from the project directory so the same `.env` file is found.

## Usage

### Command line

With the virtual environment active and configuration set, print the configured values for each matching tab:

```sh
budget sheets
```

The `sheets` command is the default, so `budget` does the same thing. Set logging verbosity with `--log-level`, for example `budget --log-level DEBUG sheets`.

Run a retirement Monte Carlo forecast:

```sh
budget retirement-forecast
```

The forecast reads historical monthly returns and inflation from `data/input/sample_returns_inflation.csv`, obtains the current balance from the spreadsheet's `Balances` tab, and estimates contributions from the latest matching budget tab. The default CSV must have `date`, `nominal_return`, and `inflation` columns. Supply another CSV or override the resolved amounts as needed:

```sh
budget retirement-forecast --csv-path /path/to/returns.csv
budget retirement-forecast --initial-balance 150000 --monthly-contribution 1200
```

Account and contribution matching defaults are `hsa,401k,roth,savings` and `hsa,401k,roth` respectively. Change them with `--account-patterns`, `--contribution-patterns`, `--contribution-fields`, or `--summary-keys` (comma-separated). If values cannot be resolved, the forecast currently falls back to built-in sample amounts; review the output before relying on it.

### Web dashboard

Start the Flask development server from the repository root:

```sh
flask --app app run
```

Open <http://127.0.0.1:5000>. The home page summarizes trends across the matching tabs; select a month for its details. The **Refresh** action clears the in-process cache and fetches data again. Data is otherwise cached for five minutes by default. For local development, use `flask --app app run --debug`.

The dashboard has no authentication and displays financial data. Keep it on a trusted machine or network; do not expose the development server directly to the public internet. For a production deployment, use a production WSGI server such as Gunicorn behind an appropriately secured web server.

### Configuration and environment

| Setting | Purpose | Default |
| --- | --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Path to service account JSON key | Required |
| `SPREADSHEET_ID` | Google spreadsheet ID | Required |
| `BUDGET_CONFIG` | Path to TOML cell mapping | Required |
| `BUDGET_CACHE_TTL` | Dashboard cache lifetime in seconds | `300` |
| `BUDGET_FETCH_WORKERS` | Parallel sheet fetch workers for dashboard | `6` |
| `BUDGET_RESULT_TIMEOUT` | Dashboard timeout per sheet future, in seconds | `20` |
| `BUDGET_FETCH_TIMEOUT` | Sheets API request timeout, in seconds | `15` |

See [Security](docs/SECURITY.md) for credential and deployment guidance.
