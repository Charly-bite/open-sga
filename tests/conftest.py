import sys
import os

# Add project root to sys.path so 'from sga_web.xxx' imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402
from sga_web.app import create_app  # noqa: E402


@pytest.fixture
def app():
    # Create the app with the TestingConfig
    app = create_app(config_name="testing")

    # Other setup can go here

    yield app

    # Clean up / teardown can go here


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
