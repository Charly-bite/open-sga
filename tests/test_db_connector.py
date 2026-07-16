"""Tests for db_connector.py - server config, ping, mount, get_db_path."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
import db_connector


@patch.dict(os.environ, {"FLASK_ENV": "development"})
def test_load_server_config_dev_mode():
    assert db_connector.load_server_config() is None


@patch.dict(os.environ, {"FLASK_ENV": ""}, clear=False)
def test_load_server_config_valid_file(tmp_path):
    cfg = {"server": {"hostname": "test"}}
    cfg_file = tmp_path / "server_config.json"
    cfg_file.write_text(json.dumps(cfg))
    result = db_connector.load_server_config(str(cfg_file))
    assert result == cfg


@patch.dict(os.environ, {}, clear=False)
def test_load_server_config_missing_file():
    result = db_connector.load_server_config("nonexistent_file.json")
    assert result is None


@patch("db_connector.subprocess.run")
def test_ping_server_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert db_connector.ping_server("192.168.1.1") is True


@patch("db_connector.subprocess.run")
def test_ping_server_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    assert db_connector.ping_server("192.168.1.1") is False


@patch("db_connector.subprocess.run", side_effect=Exception("timeout"))
def test_ping_server_exception(mock_run):
    assert db_connector.ping_server("192.168.1.1") is False


@patch("db_connector.subprocess.run")
def test_try_mount_already_connected(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    result = db_connector._try_mount(r"\\server\share", "user", "pass")
    assert result is True


@patch("db_connector.subprocess.run")
def test_try_mount_connects_successfully(mock_run):
    check_result = MagicMock(returncode=1)
    mount_result = MagicMock(returncode=0)
    mock_run.side_effect = [check_result, mount_result]
    result = db_connector._try_mount(r"\\server\share", "user", "pass")
    assert result is True


@patch("db_connector.subprocess.run")
def test_try_mount_fails(mock_run):
    check_result = MagicMock(returncode=1)
    mount_result = MagicMock(returncode=1, stderr="generic error")
    mock_run.side_effect = [check_result, mount_result]
    result = db_connector._try_mount(r"\\server\share", "user", "pass")
    assert result is False


def test_mount_share_no_config():
    assert db_connector.mount_share(None) is False


def test_mount_share_missing_fields():
    assert db_connector.mount_share({}) is False
    assert db_connector.mount_share({"server": {}}) is False


@patch.dict(os.environ, {"FLASK_ENV": "development"})
def test_get_db_path_dev_mode():
    path, source = db_connector.get_db_path(None)
    assert path == "unified_db"
    assert source == "local_development"


@patch.dict(os.environ, {}, clear=False)
def test_get_db_path_no_config():
    env = os.environ.copy()
    env.pop("FLASK_ENV", None)
    with patch.dict(os.environ, env, clear=True):
        path, source = db_connector.get_db_path(None)
        assert path == "unified_db"
        assert source == "local_default"
