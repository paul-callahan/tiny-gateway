from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from jose import jwt

from tiny_gateway.config.settings import settings
from tiny_gateway.core import security
from tiny_gateway.models.config_models import AppConfig
from tiny_gateway.models.schemas import TokenPayload


def _build_config() -> AppConfig:
    return AppConfig.from_dict(
        {
            "tenants": [{"id": "tenant-a"}],
            "users": [
                {
                    "name": "user1",
                    "password": "pass",
                    "tenant_id": "tenant-a",
                    "roles": ["admin"],
                }
            ],
            "roles": {"admin": [{"resource": "*", "actions": ["read"]}]},
            "proxy": [],
        }
    )


def test_password_hash_and_validation_paths():
    password = "super-secret"
    hashed_password = "$2b$fake-hash-value"

    with patch.object(security.pwd_context, "hash", return_value=hashed_password):
        assert security.get_password_hash(password) == hashed_password

    with patch.object(security.pwd_context, "verify", return_value=True) as mock_verify:
        assert security.verify_password(password, hashed_password) is True
        mock_verify.assert_called_once_with(password, hashed_password)

    with patch("tiny_gateway.core.security.verify_password", return_value=True) as mock_verify_password:
        assert security._validate_password(password, hashed_password) is True
        mock_verify_password.assert_called_once_with(password, hashed_password)


def test_create_access_token_uses_default_expiry():
    token = security.create_access_token(
        subject="user1",
        data={"roles": ["admin"], "tenant_id": "tenant-a"},
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "user1"
    assert payload["roles"] == ["admin"]
    assert payload["tenant_id"] == "tenant-a"
    assert payload["exp"] > int((datetime.now(UTC) + timedelta(minutes=1)).timestamp())


def test_validate_token_rejects_invalid_roles_type():
    config = _build_config()
    token = jwt.encode(
        {
            "sub": "user1",
            "tenant_id": "tenant-a",
            "roles": "admin",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        security.validate_token_and_get_payload(token, config)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_validate_token_rejects_user_not_in_config():
    config = _build_config()
    token = jwt.encode(
        {
            "sub": "missing-user",
            "tenant_id": "tenant-a",
            "roles": ["admin"],
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        security.validate_token_and_get_payload(token, config)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_validate_token_handles_unexpected_decode_error():
    config = _build_config()
    with patch("tiny_gateway.core.security.jwt.decode", side_effect=Exception("decode blew up")):
        with pytest.raises(HTTPException) as exc_info:
            security.validate_token_and_get_payload("not-used", config)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_active_user_passthrough():
    payload = TokenPayload(sub="user1", roles=["admin"], tenant_id="tenant-a")
    result = await security.get_current_active_user(payload)
    assert result == payload
