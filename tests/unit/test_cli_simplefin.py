import sys
from unittest.mock import patch

import pytest

from budget.cli import main
from budget.config import ConfigError


def test_help_lists_simplefin_commands(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["budget", "--help"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "simplefin-claim" in output
    assert "simplefin" in output
    assert "snapshot" in output


def test_simplefin_claim_prints_access_url_and_private_storage_instruction(
    monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", ["budget", "simplefin-claim", "token"])
    with patch(
        "budget.cli.claim_setup_token", return_value="https://bridge.example/u/p"
    ) as claim:
        main()

    claim.assert_called_once_with("token")
    output = capsys.readouterr().out
    assert "https://bridge.example/u/p" in output
    assert "SIMPLEFIN_ACCESS_URL" in output


def test_simplefin_requires_configured_access_url(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["budget", "simplefin"])
    with patch(
        "budget.cli.get_accounts",
        side_effect=ConfigError("missing SIMPLEFIN_ACCESS_URL"),
    ):
        with pytest.raises(ConfigError, match="SIMPLEFIN_ACCESS_URL"):
            main()


def test_snapshot_saves_fetched_accounts(monkeypatch, capsys):
    accounts = [{"name": "Savings", "balance": "12.50"}]
    monkeypatch.setattr(sys, "argv", ["budget", "snapshot"])
    with (
        patch("budget.cli.get_accounts", return_value=accounts),
        patch("budget.cli.insert_balance_snapshots") as insert,
    ):
        main()

    insert.assert_called_once_with(accounts)
    assert "Saved balance snapshot for 1 account(s)." in capsys.readouterr().out
