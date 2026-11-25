"""Authenticate legacy endpoint tests against their own in-memory data."""
import pytest

from app.core.auth import current_user
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def test_account():
    async def user():
        return User(id=1, username='test', password_hash='unused')

    app.dependency_overrides[current_user] = user
    yield
    app.dependency_overrides.pop(current_user, None)
