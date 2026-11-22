# CHANGELOG

## Unreleased

### Changes in Behavior

- The home page now reads monthly cash-flow totals from SQLite transactions rather than configured monthly Google Sheets values.
- Google Sheets remains available for legacy commands and the `/month/<sheet_name>` route.
- Added SQLite-backed balances, SimpleFIN transaction imports, transaction browsing, and a category spend chart.

### Added

- SimpleFIN setup-token claiming, mapped account balances, daily balance snapshots, and transaction upserts.
- SQLite categories, ordered categorization rules, automatic categorization on upsert, and manual category overrides.
- Transactions, rules, and balances dashboard pages plus JSON endpoints for spend and balance trends.
- Frontend TypeScript build and hover labels for spend chart categories.
- Database, categorization, deployment, route, and security documentation.

### Fixed

- SimpleFIN requests are limited to 24 per calendar day using atomic reservations in SQLite.
- Pending transactions are stored and updated when later SimpleFIN responses change their state.

### Development

- Added a TypeScript frontend build using `npm run build`.
