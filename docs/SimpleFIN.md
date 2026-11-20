# SimpleFIN

- [SimpleFIN Bridge developer guide](https://beta-bridge.simplefin.org/info/developers#limits)

Run `budget transactions` to fetch the most recent 90 days and upsert mapped
transactions into SQLite. Use `--start-date YYYY-MM-DD` and
`--end-date YYYY-MM-DD` to select a range; the start is inclusive and the end
is exclusive. SimpleFIN caps a request at 90 days. Transactions are keyed by
their SimpleFIN account and transaction IDs, so fetching overlapping ranges is
safe and updates changed (including pending) transactions.
