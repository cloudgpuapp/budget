# Transaction categorization

Rules are stored in `categorization_rules.conditions` as JSON. The current rule editor creates conditions where the transaction `description` **contains** a text value. Matching is case-insensitive.

Each condition list uses `match_type` `ALL` or `ANY`: `ALL` requires every condition to match; `ANY` requires at least one. Active rules are evaluated by ascending priority number, then ascending rule ID. The first match supplies the transaction category.

Categorization runs when SimpleFIN transactions are upserted and after a rule is saved or deleted. Existing manual category choices have `is_manual_category=1`; automatic reruns preserve those overrides. Clearing a manual category resets the override and applies the current rules. The **Run rules** action reevaluates every non-manual transaction.
