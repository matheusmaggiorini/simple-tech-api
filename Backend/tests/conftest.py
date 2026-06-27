"""Shared pytest fixtures."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.core.database import init_db
from api.endpoints import state


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    init_db()
    os.makedirs(state.UPLOAD_DIR, exist_ok=True)
    os.makedirs(state.SESSION_DIR, exist_ok=True)
