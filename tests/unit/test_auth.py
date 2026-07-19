import uuid

import pytest
from proactive_core.auth import AuthenticationError, MemorySessionStore, TokenManager
from proactive_core.config import Settings


@pytest.mark.asyncio
async def test_access_and_rotating_refresh_family() -> None:
    store = MemorySessionStore()
    manager = TokenManager(Settings(env="test"), store)
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    pair = await manager.issue(user_id=user_id, org_id=org_id, role="owner")
    principal = manager.verify_access(pair.access_token)
    assert principal.user_id == user_id
    assert principal.org_id == org_id
    rotated = await manager.rotate(pair.refresh_token)
    assert rotated.refresh_token != pair.refresh_token
    with pytest.raises(AuthenticationError, match="reuse"):
        await manager.rotate(pair.refresh_token)
    with pytest.raises(AuthenticationError):
        await manager.rotate(rotated.refresh_token)
