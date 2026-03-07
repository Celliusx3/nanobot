"""Plain .env file store for environment variables."""

from pathlib import Path


class EnvStore:
    """Read/write ~/.nanobot/.env file."""

    def __init__(self, base_dir: Path | None = None):
        self.env_path = (base_dir or Path.home() / ".nanobot") / ".env"

    def _load(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        result = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    def _save(self, data: dict[str, str]) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}" for k, v in sorted(data.items())]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.env_path.chmod(0o600)

    def set(self, key: str, value: str) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def get(self, key: str) -> str | None:
        return self._load().get(key)

    def remove(self, key: str) -> bool:
        data = self._load()
        if key not in data:
            return False
        del data[key]
        self._save(data)
        return True

    def list_keys(self) -> list[str]:
        return sorted(self._load().keys())

    def load_all(self) -> dict[str, str]:
        return self._load()
