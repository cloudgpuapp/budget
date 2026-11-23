import base64
from unittest.mock import Mock, patch

import pytest

from budget.simplefin import SimpleFINError, claim_setup_token, get_accounts


@pytest.fixture(autouse=True)
def simplefin_config(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGET_DB_PATH", str(tmp_path / "balances.sqlite3"))
    with patch(
        "budget.simplefin.load_toml", return_value={"simplefin": {"accounts": {}}}
    ):
        yield


def response(*, text="", payload=None):
    result = Mock()
    result.text = text
    result.json.return_value = payload
    result.raise_for_status.return_value = None
    return result


def test_claim_setup_token_posts_decoded_claim_url():
    token = base64.b64encode(b"https://bridge.example/claim/once").decode()
    with patch(
        "budget.simplefin.requests.post",
        return_value=response(text="https://user:secret@bridge.example/api"),
    ) as post:
        assert claim_setup_token(token) == "https://user:secret@bridge.example/api"
    assert post.call_args.args == ("https://bridge.example/claim/once",)
    assert "timeout" in post.call_args.kwargs
    assert post.call_args.kwargs["allow_redirects"] is False


def test_get_accounts_returns_balance_fields():
    payload = {
        "accounts": [
            {"id": "a1", "name": "Savings", "balance": "12.34", "balance-date": 1234}
        ]
    }
    with patch(
        "budget.simplefin.requests.get", return_value=response(payload=payload)
    ) as get:
        result = get_accounts(
            "https://user:secret@bridge.example/api", {"a1": "Josh's Schwab Savings"}
        )
    assert result == [
        {
            "id": "a1",
            "name": "Josh's Schwab Savings",
            "balance": "12.34",
            "balance_timestamp": 1234,
            "date": "1970-01-01",
        }
    ]
    assert get.call_args.args == ("https://user:secret@bridge.example/api/accounts",)
    assert get.call_args.kwargs["params"] == {"balances-only": 1}
    assert get.call_args.kwargs["allow_redirects"] is False


def test_get_accounts_returns_empty_list():
    with patch(
        "budget.simplefin.requests.get", return_value=response(payload={"accounts": []})
    ):
        assert get_accounts("https://user:secret@bridge.example/api") == []


def test_get_accounts_warns_and_skips_unmapped_accounts(caplog):
    payload = {
        "accounts": [{"id": "a1", "name": "Institution Name", "balance": "12.34"}]
    }
    with patch("budget.simplefin.requests.get", return_value=response(payload=payload)):
        assert get_accounts("https://user:secret@bridge.example/api", {}) == []
    assert "unmapped SimpleFIN account id a1" in caplog.text


@pytest.mark.parametrize("operation", ["claim", "accounts"])
def test_http_error_never_exposes_access_url(operation):
    secret_url = "https://user:secret@bridge.example/api"
    error_response = response()
    error_response.raise_for_status.side_effect = __import__("requests").HTTPError(
        f"failed at {secret_url}"
    )
    with (
        patch("budget.simplefin.requests.post", return_value=error_response),
        patch("budget.simplefin.requests.get", return_value=error_response),
    ):
        with pytest.raises(SimpleFINError) as exc:
            if operation == "claim":
                claim_setup_token(
                    base64.b64encode(b"https://bridge.example/claim/x").decode()
                )
            else:
                get_accounts(secret_url)
    assert secret_url not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_malformed_json_is_reported_without_access_url():
    secret_url = "https://user:secret@bridge.example/api"
    bad = response()
    bad.json.side_effect = __import__("requests").JSONDecodeError("bad", "{", 0)
    with patch("budget.simplefin.requests.get", return_value=bad):
        with pytest.raises(SimpleFINError) as exc:
            get_accounts(secret_url)
    assert secret_url not in str(exc.value)


def test_timeout_is_reported_without_access_url():
    import requests

    secret_url = "https://user:secret@bridge.example/api"
    with patch(
        "budget.simplefin.requests.get", side_effect=requests.Timeout(secret_url)
    ):
        with pytest.raises(SimpleFINError, match="timed out") as exc:
            get_accounts(secret_url)
    assert secret_url not in str(exc.value)


def test_access_url_is_loaded_from_environment():
    with (
        patch(
            "budget.simplefin.get_env",
            return_value="https://user:secret@bridge.example/api",
        ) as get_env,
        patch(
            "budget.simplefin.requests.get",
            return_value=response(payload={"accounts": []}),
        ),
    ):
        assert get_accounts(account_names={}) == []
    get_env.assert_called_once_with("SIMPLEFIN_ACCESS_URL")


@pytest.mark.parametrize("url", ["http://bridge.example/claim", "https://"])
def test_claim_rejects_non_https_token_without_request(url):
    token = base64.b64encode(url.encode()).decode()
    with patch("budget.simplefin.requests.post") as post:
        with pytest.raises(SimpleFINError, match="Invalid SimpleFIN setup token"):
            claim_setup_token(token)
    post.assert_not_called()


def test_get_accounts_rejects_http_access_url_without_request():
    with patch("budget.simplefin.requests.get") as get:
        with pytest.raises(SimpleFINError, match="malformed account data"):
            get_accounts("http://user:secret@bridge.example/api")
    get.assert_not_called()


def test_errlist_is_reported_without_access_url(monkeypatch, tmp_path):
    secret_url = "https://user:secret@bridge.example/api"
    monkeypatch.setenv("BUDGET_DB_PATH", str(tmp_path / "balances.sqlite3"))
    with patch(
        "budget.simplefin.requests.get",
        return_value=response(
            payload={"accounts": [], "errlist": [f"bad account at {secret_url}"]}
        ),
    ):
        with pytest.raises(SimpleFINError, match="bad account") as exc:
            get_accounts(secret_url)
    assert secret_url not in str(exc.value)


@pytest.mark.parametrize("operation", ["claim", "accounts"])
def test_http_status_is_reported_without_secret_url(operation, monkeypatch, tmp_path):
    import requests

    secret_url = "https://user:secret@bridge.example/api"
    monkeypatch.setenv("BUDGET_DB_PATH", str(tmp_path / "balances.sqlite3"))
    failed = response()
    failed.status_code = 403
    failed.raise_for_status.side_effect = requests.HTTPError(
        secret_url, response=failed
    )
    with (
        patch("budget.simplefin.requests.post", return_value=failed),
        patch("budget.simplefin.requests.get", return_value=failed),
    ):
        with pytest.raises(SimpleFINError) as exc:
            if operation == "claim":
                claim_setup_token(
                    base64.b64encode(b"https://bridge.example/claim").decode()
                )
            else:
                get_accounts(secret_url)
    assert "403" in str(exc.value)
    assert secret_url not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_daily_request_limit_is_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGET_DB_PATH", str(tmp_path / "balances.sqlite3"))
    # This test verifies the documented default cap, regardless of the caller's env.
    monkeypatch.delenv("SIMPLEFIN_DAILY_REQUEST_LIMIT", raising=False)
    with patch(
        "budget.simplefin.requests.get", return_value=response(payload={"accounts": []})
    ) as get:
        for _ in range(24):
            assert get_accounts("https://user:secret@bridge.example/api", {}) == []
        with pytest.raises(SimpleFINError, match="daily request limit"):
            get_accounts("https://user:secret@bridge.example/api", {})
    assert get.call_count == 24
