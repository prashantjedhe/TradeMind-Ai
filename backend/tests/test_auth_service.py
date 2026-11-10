import uuid
import pytest
from jose import JWTError

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_password_hashing_and_verification():
    plain = "SuperSecretTraderPass123!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_and_refresh_token_generation():
    user_id = str(uuid.uuid4())

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    payload_access = decode_token(access_token)
    payload_refresh = decode_token(refresh_token)

    assert payload_access["sub"] == user_id
    assert payload_access["type"] == "access"
    assert "jti" in payload_access
    assert "exp" in payload_access

    assert payload_refresh["sub"] == user_id
    assert payload_refresh["type"] == "refresh"


def test_invalid_token_raises_jwt_error():
    with pytest.raises(JWTError):
        decode_token("invalid.token.payload")
