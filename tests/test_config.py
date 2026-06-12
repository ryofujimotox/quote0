"""config.py の単体テスト。"""

from __future__ import annotations

import pytest

from quote0.config import ConfigError, load_config


REQUIRED_ENV_NAMES = ("ICAL_URLS", "DOT_API_TOKEN", "DOT_DEVICE_ID")


def clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """必須環境変数をテストごとに消す。"""
    for name in REQUIRED_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_config_fails_when_ical_urls_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clear_required_env(monkeypatch)
    monkeypatch.setenv("DOT_API_TOKEN", "token")
    monkeypatch.setenv("DOT_DEVICE_ID", "device")

    with pytest.raises(ConfigError, match="ICAL_URLS が未設定"):
        load_config(tmp_path / ".env")


def test_load_config_fails_when_dot_api_token_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clear_required_env(monkeypatch)
    monkeypatch.setenv("ICAL_URLS", "https://example.com/a.ics")
    monkeypatch.setenv("DOT_DEVICE_ID", "device")

    with pytest.raises(ConfigError, match="DOT_API_TOKEN が未設定"):
        load_config(tmp_path / ".env")


def test_load_config_fails_when_dot_device_id_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clear_required_env(monkeypatch)
    monkeypatch.setenv("ICAL_URLS", "https://example.com/a.ics")
    monkeypatch.setenv("DOT_API_TOKEN", "token")

    with pytest.raises(ConfigError, match="DOT_DEVICE_ID が未設定"):
        load_config(tmp_path / ".env")


def test_load_config_splits_ical_urls_in_order(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clear_required_env(monkeypatch)
    monkeypatch.setenv("ICAL_URLS", " https://example.com/a.ics,https://example.com/b.ics ")
    monkeypatch.setenv("DOT_API_TOKEN", " token ")
    monkeypatch.setenv("DOT_DEVICE_ID", " device ")

    config = load_config(tmp_path / ".env")

    assert config.ical_urls == ("https://example.com/a.ics", "https://example.com/b.ics")
    assert config.dot_api_token == "token"
    assert config.dot_device_id == "device"
    assert config.debug is False


@pytest.mark.parametrize("value", ("1", "true", "TRUE", "yes", "on"))
def test_load_config_enables_debug_from_env_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    value: str,
) -> None:
    clear_required_env(monkeypatch)
    monkeypatch.setenv("ICAL_URLS", "https://example.com/a.ics")
    monkeypatch.setenv("DOT_API_TOKEN", "token")
    monkeypatch.setenv("DOT_DEVICE_ID", "device")
    monkeypatch.setenv("QUOTE0_DEBUG", value)

    config = load_config(tmp_path / ".env")

    assert config.debug is True
