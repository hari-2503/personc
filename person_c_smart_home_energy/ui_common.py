"""Shared HTTP helpers for Person C's Streamlit frontend.

The UI is a pure REST client: it only talks to the FastAPI backend over HTTP.
"""
from typing import Any, Optional

import requests

DEFAULT_TIMEOUT = (3, 10)


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _handle(response: requests.Response) -> tuple[bool, Any]:
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        return False, f"HTTP {response.status_code}: {detail}"
    return True, response.json() if response.content else {}


def api_get(base_url: str, path: str, params: Optional[dict] = None) -> tuple[bool, Any]:
    try:
        response = requests.get(_url(base_url, path), params=params, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"Cannot reach API ({exc.__class__.__name__})"
    return _handle(response)


def api_post(base_url: str, path: str, json_body: dict) -> tuple[bool, Any]:
    try:
        response = requests.post(_url(base_url, path), json=json_body, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"Cannot reach API ({exc.__class__.__name__})"
    return _handle(response)


def api_put(base_url: str, path: str, json_body: dict) -> tuple[bool, Any]:
    try:
        response = requests.put(_url(base_url, path), json=json_body, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"Cannot reach API ({exc.__class__.__name__})"
    return _handle(response)


def api_delete(base_url: str, path: str) -> tuple[bool, Any]:
    try:
        response = requests.delete(_url(base_url, path), timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"Cannot reach API ({exc.__class__.__name__})"
    return _handle(response)


def money(value: float, currency: str = "INR") -> str:
    return f"{currency} {value:,.2f}"
