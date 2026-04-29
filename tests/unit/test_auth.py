"""Unit tests for authentication helpers and dependencies."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.main import get_current_tenant


async def test_get_current_tenant_rejects_missing_api_key() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant(api_key=None, db=AsyncMock())

    assert exc_info.value.status_code == 401
