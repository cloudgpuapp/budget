# Database, backup, and restore

SQLite is the system of record for imported transactions and balance history. The path comes from `BUDGET_DB_PATH`; otherwise it is `~/.local/share/budget/balances.sqlite3`, or `$XDG_DATA_HOME/budget/balances.sqlite3` when `XDG_DATA_HOME` is set. SQLite uses WAL mode and foreign keys.

The current schema sets `PRAGMA user_version = 3`:

| Table | Contents |
| --- | --- |
| `balance_snapshots` | Per-account dated balances and their `manual` or `simplefin` source. |
| `simplefin_request_counts` | Daily request count used to enforce the 24-request limit. |
| `accounts` | SimpleFIN account IDs and configured display names. |
| `transactions` | Upserted transactions, pending state, dates, category and manual-override fields. |
| `categories` | User-defined transaction categories. |
| `categorization_rules` | Ordered active/inactive rules and their JSON conditions. |

Schema setup and migrations happen in `balances_db._connect()`: it creates missing tables/indexes, checks existing columns, applies additive changes with `ALTER TABLE`, then sets `user_version` to 3. Keep a backup before replacing the application with a version that changes the schema.

## Backup and restore

Stop the app and snapshot timer before copying the database, including any matching `-wal` and `-shm` files. A safe live backup can be made with SQLite's online backup API, for example:

```sh
sqlite3 "$BUDGET_DB_PATH" ".backup '/path/to/budget-backup.sqlite3'"
```

Keep backups encrypted and outside the repository. To restore, stop the app and timer, replace the configured database with the backup file, then restart the services. Verify the restored file is readable by opening `/balances` and `/transactions`.

To erase local cached records after disconnecting SimpleFIN, stop the services and delete the configured SQLite database and its `-wal`/`-shm` sidecars. This deletes local balances, transactions, categories, rules, and request counts together. It does not revoke the Bridge Access URL; revoke that separately in SimpleFIN Bridge. For selective deletion, delete transactions and account records through SQLite with foreign keys enabled, and remove related balance snapshots separately.
