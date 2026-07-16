"""Tests for sga_web/config.py - configuration classes and helpers."""

import os
import pytest
from unittest.mock import patch, mock_open
from sga_web.config import (
    Config,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    config,
    get_sql_connection_string,
    _generate_secret_key,
)


def test_config_mapping_has_required_keys():
    assert "development" in config
    assert "production" in config
    assert "testing" in config
    assert "default" in config


def test_config_mapping_classes():
    assert config["development"] is DevelopmentConfig
    assert config["production"] is ProductionConfig
    assert config["testing"] is TestingConfig


def test_development_config():
    assert DevelopmentConfig.DEBUG is True
    assert DevelopmentConfig.TESTING is False


def test_production_config():
    assert ProductionConfig.DEBUG is False
    assert ProductionConfig.SESSION_COOKIE_SECURE is True


def test_testing_config():
    assert TestingConfig.DEBUG is True
    assert TestingConfig.TESTING is True
    assert TestingConfig.WTF_CSRF_ENABLED is False


def test_base_config_has_secret_key():
    assert Config.SECRET_KEY is not None
    assert len(Config.SECRET_KEY) > 0


def test_base_config_session_settings():
    assert Config.SESSION_COOKIE_HTTPONLY is True
    assert Config.SESSION_COOKIE_SAMESITE == "Lax"


def test_base_config_pagination():
    assert Config.ITEMS_PER_PAGE == 25


@patch.dict(
    os.environ,
    {
        "SQL_SERVER": "10.0.0.1",
        "SQL_DATABASE": "TestDB",
        "SQL_USER": "testuser",
        "SQL_PASSWORD": "testpass",
        "SQL_TRUST_CERTIFICATE": "no",
    },
)
def test_get_sql_connection_string_with_odbc17():
    conn = get_sql_connection_string()
    assert "SERVER=10.0.0.1" in conn
    assert "DATABASE=TestDB" in conn
    assert "TrustServerCertificate=no" in conn


@patch.dict(
    os.environ,
    {
        "SQL_SERVER": "10.0.0.1",
        "SQL_DATABASE": "TestDB",
        "SQL_USER": "testuser",
        "SQL_PASSWORD": "testpass",
    },
)
def test_get_sql_connection_string_legacy_driver():
    conn = get_sql_connection_string(driver="{SQL Server}")
    assert "TrustServerCertificate" not in conn


@patch.dict(os.environ, {"SQL_PASSWORD": ""}, clear=False)
def test_get_sql_connection_string_missing_password():
    with pytest.raises(ValueError, match="Missing SQL_PASSWORD"):
        get_sql_connection_string()


@patch.dict(os.environ, {"SECRET_KEY": "my-env-secret"})
def test_generate_secret_key_from_env():
    assert _generate_secret_key() == "my-env-secret"


@patch.dict(os.environ, {}, clear=True)
@patch("builtins.open", mock_open(read_data="file-secret-key"))
@patch("os.path.exists", return_value=True)
def test_generate_secret_key_from_file(mock_exists):
    assert _generate_secret_key() == "file-secret-key"


@patch.dict(os.environ, {}, clear=True)
@patch("os.path.exists", return_value=False)
def test_generate_secret_key_generates_new(mock_exists):
    with patch("builtins.open", mock_open()):
        key = _generate_secret_key()
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)
