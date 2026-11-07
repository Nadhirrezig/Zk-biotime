"""DB password storage in the OS keyring (Windows Credential Manager). Never in SQLite."""
from __future__ import annotations

import keyring
from keyring.errors import KeyringError

SERVICE = "zkreport"


class SecretStoreError(RuntimeError):
    pass


def get_password(account: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, account)
    except Exception:  # no backend available: behave as "no password"
        return None


def set_password(account: str, password: str | None) -> None:
    if not password:
        try:
            keyring.delete_password(SERVICE, account)
        except Exception:  # nothing stored or no backend: nothing to delete
            pass
        return
    try:
        keyring.set_password(SERVICE, account, password)
    except KeyringError as exc:
        raise SecretStoreError(str(exc)) from exc
