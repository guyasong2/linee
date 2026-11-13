from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _load_dotenv() -> None:
    """Load a local .env without overriding values supplied by the environment."""
    if os.environ.get("LINE_SKIP_DOTENV") == "1":
        return

    default_path = Path(__file__).resolve().parent.parent / ".env"
    path = Path(os.environ.get("LINE_ENV_FILE", default_path))
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def env(key: str, default: Any = None, *, required: bool = False) -> Any:
    value = os.environ.get(key, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Required environment variable {key!r} is not set")
    return value


def env_bool(key: str, default: bool = False, *, required: bool = False) -> bool:
    value = env(key, default, required=required)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int = 0, *, required: bool = False) -> int:
    value = env(key, default, required=required)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Environment variable {key!r} must be an integer") from exc


def env_list(key: str, default: str = "", *, required: bool = False) -> list[str]:
    value = env(key, default, required=required)
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]
