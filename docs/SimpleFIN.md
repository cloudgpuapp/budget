# SimpleFIN

See the [SimpleFIN Bridge developer guide](https://beta-bridge.simplefin.org/info/developers#limits) and [protocol](https://www.simplefin.org/protocol-v1.html).

## Claiming and setup

Create a one-time Setup Token in SimpleFIN Bridge and run:

```sh
budget simplefin-claim '<setup-token>'
```

The command posts to the token's HTTPS claim URL without following redirects and prints the resulting Access URL. Store it privately as `SIMPLEFIN_ACCESS_URL`; treat it as a bearer credential. The token is single-use.

Every account ID must be mapped in `config.toml`:

```toml
[simplefin.accounts]
"raw-account-id-from-Bridge" = "Display name"
```

The app skips unmapped accounts. To list raw account IDs before creating the mapping, run `budget simplefin --list-raw-ids`. Then add the desired IDs to `[simplefin.accounts]`.

## Fetching balances and transactions

- `budget simplefin` fetches and displays balances for mapped accounts.
- `budget snapshot` saves mapped account balances to `balance_snapshots` with source `simplefin`.
- `budget transactions` upserts mapped transactions to SQLite. Its default window is the most recent 90 days. `--start-date` is inclusive and `--end-date` exclusive; longer windows are fetched in consecutive requests of up to 90 days each. Each request counts against the daily SimpleFIN request limit.

The client reserves each all-account API request in SQLite before sending it and enforces a maximum of 24 requests per calendar day by default. Set `SIMPLEFIN_DAILY_REQUEST_LIMIT` to a positive integer to choose a different cap (for example, `12`). The cap is enforced independently in each configured `BUDGET_DB_PATH`; separate Pi and Mac databases do not share or coordinate their counts. A failed request still consumes a reserved slot. Requests require HTTPS and redirects are refused. Transaction upserts use account ID plus transaction ID, so overlapping imports update existing records rather than duplicate them. Pending transactions are stored; a later fetch can update a transaction as it posts or changes.

Categorization runs after transaction upserts. Active rules apply by priority, and manual category overrides are preserved. See [Categorization](CATEGORIZATION.md).
