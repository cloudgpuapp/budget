"""Small SimpleFIN Bridge client for claiming tokens and reading balances.

SimpleFIN's protocol specification does not prescribe a rate limit. The
SimpleFIN Bridge developer guide expects at most 24 all-account requests per
day per access token (with some leeway during initial setup); excess requests
can lead to warnings and eventual token disablement. See
https://beta-bridge.simplefin.org/info/developers#limits.
"""

import base64
import binascii
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from budget.config import get_env

_FETCH_TIMEOUT = int(os.environ.get("BUDGET_FETCH_TIMEOUT", 15))


class SimpleFINError(Exception):
    """An error communicating with SimpleFIN, without credential-bearing URLs."""


def _request_error(action: str, exc: Exception) -> SimpleFINError:
    if isinstance(exc, requests.Timeout):
        return SimpleFINError(f"SimpleFIN {action} request timed out")
    if isinstance(exc, requests.HTTPError):
        return SimpleFINError(f"SimpleFIN {action} request returned an HTTP error")
    return SimpleFINError(f"SimpleFIN {action} request failed")


def claim_setup_token(setup_token: str) -> str:
    """Claim a base64-encoded one-time setup token and return its access URL."""
    try:
        claim_url = base64.b64decode(setup_token, validate=True).decode("utf-8").strip()
        parsed = urlsplit(claim_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("not an HTTP URL")
    except (ValueError, UnicodeDecodeError, binascii.Error, TypeError):
        raise SimpleFINError("Invalid SimpleFIN setup token") from None

    try:
        response = requests.post(claim_url, timeout=_FETCH_TIMEOUT)
        response.raise_for_status()
        access_url = response.text.strip()
        access_parts = urlsplit(access_url)
        if access_parts.scheme not in ("http", "https") or not access_parts.netloc:
            raise SimpleFINError("SimpleFIN returned an invalid access URL")
        return access_url
    except SimpleFINError:
        raise
    except requests.RequestException as exc:
        raise _request_error("claim", exc) from None


def get_accounts(access_url: str | None = None) -> list[dict[str, Any]]:
    """Fetch account ids, names, balances, and balance timestamps.

    If ``access_url`` is omitted, it is read from ``SIMPLEFIN_ACCESS_URL``.
    """
    if access_url is None:
        access_url = get_env("SIMPLEFIN_ACCESS_URL")
    try:
        parts = urlsplit(access_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("invalid access URL")
        endpoint = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/accounts", "", ""))
        response = requests.get(
            endpoint,
            params={"balances-only": 1},
            timeout=_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        accounts = payload["accounts"]
        if not isinstance(accounts, list):
            raise ValueError("accounts is not a list")
        return [
            {
                "id": account["id"],
                "name": account["name"],
                "balance": account["balance"],
                "balance_timestamp": account.get("balance-date"),
            }
            for account in accounts
        ]
    except requests.exceptions.JSONDecodeError:
        raise SimpleFINError("SimpleFIN returned malformed account data") from None
    except requests.RequestException as exc:
        raise _request_error("accounts", exc) from None
    except (ValueError, KeyError, TypeError, AttributeError):
        # requests' JSONDecodeError may retain the response URL, so don't chain it.
        raise SimpleFINError("SimpleFIN returned malformed account data") from None
