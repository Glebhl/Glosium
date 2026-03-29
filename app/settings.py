from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml


class YAMLConfig:
    def __init__(self, file_path: str):
        """Initialize the config store for a YAML file."""
        self.file_path = Path(file_path)
        self._data = self._load()

    def _load(self) -> dict:
        """Load configuration data from disk."""
        if not self.file_path.exists():
            return {}
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    def _save(self):
        """Persist the current configuration to disk."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, sort_keys=False)

    def get_value(self, path: str, default: Any = None) -> Any:
        """Return a nested value by slash-separated path."""
        keys = path.split("/")
        current = self._data

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def set_value(self, path: str, value: Any):
        """Set a nested value and save the updated config."""
        keys = path.split("/")
        current = self._data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        self._save()


_settings_store = YAMLConfig("settings.yaml")


def get_settings_store() -> YAMLConfig:
    """Return the shared application settings store."""
    return _settings_store
