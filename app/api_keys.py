from __future__ import annotations

from typing import Any

import keyring


class KeyringConfig:
    def __init__(self, service_name: str):
        """Initialize the config store for secrets in the OS keyring."""
        self.service_name = service_name

    def get_value(self, path: str, default: Any = None) -> Any:
        """Return a stored secret by slash-separated path."""
        value = keyring.get_password(self.service_name, path)
        if value is None:
            return default
        return value

    def set_value(self, path: str, value: Any):
        """Set a secret value in the OS keyring."""
        if value is None:
            self.delete_value(path)
            return
        keyring.set_password(self.service_name, path, str(value))

    def delete_value(self, path: str) -> None:
        """Delete a stored secret from the OS keyring."""
        try:
            keyring.delete_password(self.service_name, path)
        except keyring.errors.PasswordDeleteError:
            return


_api_keys_store = KeyringConfig("Glosium")


def get_api_keys_store() -> KeyringConfig:
    """Return the shared application API keys store."""
    return _api_keys_store
