"""Tests for ${VAR} expansion in AppConfig.resolve_env_variables."""

import pytest

from deerflow.config.app_config import AppConfig


def test_resolve_braced_env_vars_in_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEER_FLOW_POSTGRES_USER", "u1")
    monkeypatch.setenv("DEER_FLOW_POSTGRES_PASSWORD", "p1")
    monkeypatch.setenv("DEER_FLOW_POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("DEER_FLOW_POSTGRES_PORT", "5432")
    monkeypatch.setenv("DEER_FLOW_POSTGRES_DB", "appdb")
    raw = (
        "postgresql://${DEER_FLOW_POSTGRES_USER}:${DEER_FLOW_POSTGRES_PASSWORD}"
        "@${DEER_FLOW_POSTGRES_HOST}:${DEER_FLOW_POSTGRES_PORT}/${DEER_FLOW_POSTGRES_DB}"
    )
    out = AppConfig.resolve_env_variables(raw)
    assert out == "postgresql://u1:p1@db.internal:5432/appdb"


def test_resolve_whole_string_env_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_SECRET", "abc123")
    assert AppConfig.resolve_env_variables("$MY_SECRET") == "abc123"


def test_resolve_braced_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEER_FLOW_POSTGRES_USER", raising=False)
    with pytest.raises(ValueError, match="DEER_FLOW_POSTGRES_USER"):
        AppConfig.resolve_env_variables("postgresql://${DEER_FLOW_POSTGRES_USER}@localhost/db")
