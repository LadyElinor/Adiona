"""Versioned, deliberately restricted canonical JSON (not RFC 8785)."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class Rejected(ValueError):
    """A request failed a declared contract; no permission is implied."""


def _check(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise Rejected("JSON nesting limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int and -(2**63) <= value < 2**63:
        return
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise Rejected("invalid Unicode") from exc
        return
    if type(value) is list:
        for item in value:
            _check(item, depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for k, item in value.items():
            _check(k, depth + 1)
            _check(item, depth + 1)
        return
    raise Rejected("only bounded integers, strings, booleans, null, arrays and objects are supported")


def canonical(value: Any) -> str:
    _check(value)
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > 262144:
        raise Rejected("JSON size limit exceeded")
    return text


def loads(text: str) -> Any:
    if type(text) is not str:
        raise Rejected("JSON input must be text")
    try:
        encoded = text.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise Rejected("invalid Unicode") from exc
    if len(encoded) > 262144:
        raise Rejected("invalid JSON input size")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in items:
            if k in out:
                raise Rejected("duplicate JSON key")
            out[k] = v
        return out

    try:
        value = json.loads(text, object_pairs_hook=pairs)
        canonical(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Rejected(f"invalid restricted JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def exact(value: Any, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise Rejected("missing or unknown fields")


def text(value: Any) -> None:
    if type(value) is not str or not value.strip():
        raise Rejected("nonempty text required")


def natural(value: Any) -> None:
    if type(value) is not int or not 0 <= value < 2**63:
        raise Rejected("nonnegative integer required")


def sha(value: Any) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise Rejected("SHA-256 hex digest required")
