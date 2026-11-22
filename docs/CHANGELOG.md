# CHANGELOG

## Unreleased

### Added

- Hover over a spend chart category to see its name.

### Development

- Migrated the frontend to TypeScript and added the `npm run build` bundle step.

## v0.1.0

### Added

- SimpleFIN setup-token claiming, mapped account balances, daily SQLite balance snapshots, and
  transaction imports.
- SQLite categories, ordered categorization rules, automatic categorization on transaction upsert,
  and manual category overrides.
- Transactions, rules, and balances dashboard pages, including a category spend chart and balance
  history.
- JSON endpoints for spend and balance trends.

### Fixed

- Enforced the daily SimpleFIN request limit with atomic SQLite reservations.
- Preserved pending-transaction updates when repeated imports return changed transaction state.
