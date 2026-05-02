"""Unit tests for authentication helpers and dependencies."""

from unittest.mock import AsyncMock

import pytest

from app.api.dependencies.auth import get_current_tenant
from app.core.exceptions import AuthenticationError


async def test_get_current_tenant_rejects_missing_api_key() -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        await get_current_tenant(api_key=None, db=AsyncMock())

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "AUTHENTICATION_FAILED"
