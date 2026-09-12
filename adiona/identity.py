"""Fixture authentication, not a process isolation or public-key infrastructure.

HMAC verification keys can also sign. Keep this entire keyring in the trusted
host; production integrations need separately administered signing services.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import secrets
from typing import Any, Mapping

from .canonical import Rejected, canonical, exact, loads, text


@dataclass(frozen=True)
class Credential:
    principal: str
    secret: bytes


@dataclass(frozen=True)
class Principal:
    role: str
    trust_domain: str


@dataclass(frozen=True)
class Envelope:
    principal: str
    purpose: str
    payload: str
    mac: str

    def body(self) -> dict[str, Any]:
        value = loads(self.payload)
        if type(value) is not dict or canonical(value) != self.payload:
            raise Rejected("noncanonical envelope")
        return value

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Envelope:
        exact(value, {"principal", "purpose", "payload", "mac"})
        if not all(type(v) is str for v in value.values()):
            raise Rejected("envelope fields must be strings")
        return cls(**value)


class Keyring:
    """Trusted-host registry. Workers must not receive this object."""

    def __init__(self, entries: Mapping[str, tuple[Principal, bytes]]):
        self._entries = dict(entries)
        for name, (principal, secret) in self._entries.items():
            text(name)
            text(principal.role)
            text(principal.trust_domain)
            if type(secret) is not bytes or len(secret) < 32:
                raise Rejected("each fixture principal needs at least 256 random key bits")
        if len({key for _, key in self._entries.values()}) != len(self._entries):
            raise Rejected("credential keys must not be shared")

    def principal(self, name: str) -> Principal:
        try:
            return self._entries[name][0]
        except (KeyError, TypeError) as exc:
            raise Rejected("unknown principal") from exc

    def authenticate(self, credential: Credential, role: str) -> Principal:
        if not isinstance(credential, Credential):
            raise Rejected("a name is not a credential")
        principal = self.principal(credential.principal)
        if type(credential.secret) is not bytes or not hmac.compare_digest(
            self._entries[credential.principal][1], credential.secret
        ):
            raise Rejected("bad credential")
        if principal.role != role:
            raise Rejected("wrong authenticated role")
        return principal

    def distinct(self, first: str, *others: str) -> None:
        for second in others:
            if first == second or self.principal(first).trust_domain == self.principal(second).trust_domain:
                raise Rejected("required fixture trust-domain separation is absent")

    @staticmethod
    def _message(principal: str, purpose: str, payload: str) -> bytes:
        return canonical({"scheme": "adiona-hmac-v1", "principal": principal,
                          "purpose": purpose, "payload": payload}).encode("utf-8")

    def sign(self, credential: Credential, purpose: str, body: dict[str, Any]) -> Envelope:
        role = self.principal(credential.principal).role
        self.authenticate(credential, role)
        text(purpose)
        payload = canonical(body)
        mac = hmac.new(credential.secret, self._message(credential.principal, purpose, payload), hashlib.sha256).hexdigest()
        return Envelope(credential.principal, purpose, payload, mac)

    def verify(self, envelope: Envelope, purpose: str, role: str) -> dict[str, Any]:
        if not isinstance(envelope, Envelope) or envelope.purpose != purpose:
            raise Rejected("wrong envelope type or purpose")
        principal = self.principal(envelope.principal)
        if principal.role != role:
            raise Rejected("signer lacks the required role")
        expected = hmac.new(self._entries[envelope.principal][1],
                            self._message(envelope.principal, purpose, envelope.payload), hashlib.sha256).hexdigest()
        if type(envelope.mac) is not str or not hmac.compare_digest(expected, envelope.mac):
            raise Rejected("invalid authentication tag")
        return envelope.body()


def demo_identities() -> tuple[Keyring, dict[str, Credential]]:
    """Generate fresh local-only credentials. No real identity or independence claim."""
    roles = {"worker": "worker", "norms": "normative", "evidence": "epistemic",
             "decider": "decider", "authorizer": "authorizer", "executor": "executor",
             "human": "human", "root": "root"}
    credentials = {name: Credential(name, secrets.token_bytes(32)) for name in roles}
    entries = {name: (Principal(role, f"fixture:{name}"), credentials[name].secret)
               for name, role in roles.items()}
    return Keyring(entries), credentials
