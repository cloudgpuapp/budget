# Deployment

Use Gunicorn behind a trusted reverse proxy or VPN. The app has no authentication or CSRF protection, and its category/rule routes change data.

Example command:

```sh
.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
```

Set a stable, random `FLASK_SECRET_KEY` in the service environment. Without it, each process generates a different key at startup, so flash messages can fail when requests move between Gunicorn workers and sessions become invalid after restarts.

Set `BUDGET_DB_PATH` to a persistent location writable by the service user. Back up this SQLite file regularly; it is the system of record for imported transactions and balances. See [Database, backup, and restore](DATABASE.md). Keep `.env`, the SimpleFIN Access URL, and any legacy service-account key private with restrictive file permissions.

## Example snapshot systemd units

The repository's deployment files are gitignored. These sanitized examples run the daily SimpleFIN balance snapshot at 04:00 local time with up to a 30 minute random delay. Adjust user and paths.

`/etc/systemd/system/budget-snapshot.service`:

```ini
[Unit]
Description=Save a daily SimpleFIN balance snapshot
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=budget
WorkingDirectory=/opt/budget
EnvironmentFile=/opt/budget/.env
ExecStart=/opt/budget/.venv/bin/budget snapshot
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
```

`/etc/systemd/system/budget-snapshot.timer`:

```ini
[Unit]
Description=Run the SimpleFIN balance snapshot daily

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true
RandomizedDelaySec=30min
Unit=budget-snapshot.service

[Install]
WantedBy=timers.target
```

Enable the timer with `systemctl daemon-reload && systemctl enable --now budget-snapshot.timer`. The app enforces the daily SimpleFIN request limit centrally in SQLite.
