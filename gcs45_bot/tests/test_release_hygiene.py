from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_RUNTIME_FILES = (
    "Dockerfile",
    "fly.toml",
    "pyproject.toml",
    "bot/models/user.py",
    "bot/models/session_record.py",
    "bot/repositories/user_repo.py",
    "bot/services/shared.py",
)

REQUIRED_RUNTIME_MODULES = (
    "bot.models.user",
    "bot.models.session_record",
    "bot.repositories.user_repo",
    "bot.services.shared",
)


def test_required_release_files_exist() -> None:
    missing = [path for path in REQUIRED_RUNTIME_FILES if not (ROOT / path).exists()]
    assert missing == []


def test_required_runtime_modules_have_specs() -> None:
    missing = [module for module in REQUIRED_RUNTIME_MODULES if importlib.util.find_spec(module) is None]
    assert missing == []
