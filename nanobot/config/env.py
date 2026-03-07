"""Encrypted environment variable store with per-skill namespacing."""

import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class EnvStore:
    """Read/write ~/.nanobot/.env.json with Fernet-encrypted values, namespaced by skill."""

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or Path.home() / ".nanobot"
        self.env_path = self._base / ".env.json"
        self._key_path = self._base / ".secret_key"
        self._fernet: Fernet | None = None

    def set(self, skill_name: str, key: str, value: str) -> None:
        data = self._load_raw()
        data.setdefault(skill_name, {})[key] = self._encrypt(value)
        self._save_raw(data)

    def get(self, skill_name: str, key: str) -> str | None:
        raw = self._load_raw().get(skill_name, {}).get(key)
        if raw is None:
            return None
        return self._decrypt(raw)

    def remove(self, skill_name: str, key: str) -> bool:
        data = self._load_raw()
        skill_data = data.get(skill_name, {})
        if key not in skill_data:
            return False
        del skill_data[key]
        if not skill_data:
            del data[skill_name]
        self._save_raw(data)
        return True

    def list_keys(self, skill_name: str | None = None) -> list[str]:
        data = self._load_raw()
        if skill_name:
            return sorted(data.get(skill_name, {}).keys())
        return sorted(data.keys())

    def load_all(self, skill_name: str) -> dict[str, str]:
        """Load all decrypted vars for a specific skill."""
        return {k: self._decrypt(v) for k, v in self._load_raw().get(skill_name, {}).items()}

    # -- key management --

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._load_or_create_key())
        return self._fernet

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_bytes(key)
        self._key_path.chmod(0o600)
        return key

    # -- encryption --

    def _encrypt(self, plaintext: str) -> str:
        return self._get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")

    def _decrypt(self, token: str) -> str:
        try:
            return self._get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return token

    # -- file I/O --

    def _load_raw(self) -> dict:
        if not self.env_path.exists():
            return {}
        return json.loads(self.env_path.read_text(encoding="utf-8"))

    def _save_raw(self, data: dict) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.env_path.chmod(0o600)
