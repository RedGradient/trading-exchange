"""Password verification, JWT tokens, and user authentication."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_sessions import RefreshSession
from app.models.users import User
from app.schemas.auth import Credentials, TokenResponse, UserResponse

_PASSWORD_ITERATIONS = 600_000


class InvalidCredentialsError(Exception):
    pass


class AuthConfigurationError(Exception):
    pass


class UsernameAlreadyExistsError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    # Keep password derivation equally expensive for unknown and legacy users.
    encoded = (
        password_hash or f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${'0' * 32}${'0' * 64}"
    )
    _, iterations, salt, expected = encoded.split("$")
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), expected) and password_hash is not None


def get_signing_key() -> str:
    if settings.jwt_secret_key is None:
        raise AuthConfigurationError()
    return settings.jwt_secret_key.get_secret_value()


def decode_token(token: str, token_type: str = "access") -> dict:
    key = get_signing_key()
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
        if claims.get("token_type", "access") != token_type:
            raise InvalidCredentialsError()
        subject = claims["sub"]
        if (
            not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdecimal()
        ):
            raise InvalidCredentialsError()
        user_id = int(subject)
        if not 0 < user_id <= 2_147_483_647:
            raise InvalidCredentialsError()
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise InvalidCredentialsError() from exc

    return claims


async def get_user_from_token(
    token: str, session: AsyncSession, token_type: str = "access"
) -> User:
    claims = decode_token(token, token_type)
    user = await session.get(User, int(claims["sub"]))
    if user is None:
        raise InvalidCredentialsError()
    return user


async def register_user(
    credentials: Credentials, session: AsyncSession
) -> UserResponse:
    password_hash = await asyncio.to_thread(
        hash_password, credentials.password.get_secret_value()
    )
    user = User(username=credentials.username, password_hash=password_hash)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UsernameAlreadyExistsError() from exc
    return UserResponse(id=user.id, username=credentials.username)


async def login(
    credentials: Credentials, session: AsyncSession, key: str
) -> tuple[TokenResponse, str]:
    user = await session.scalar(
        select(User).where(User.username == credentials.username)
    )
    password_valid = await asyncio.to_thread(
        verify_password,
        credentials.password.get_secret_value(),
        user.password_hash if user is not None else None,
    )
    if not password_valid or user is None:
        raise InvalidCredentialsError()
    access_token = create_access_token(user.id, key)
    refresh_session = create_refresh_session(user.id, session)
    refresh_token = create_refresh_token(refresh_session, key)
    await session.commit()
    return access_token, refresh_token


def create_access_token(user_id: int, key: str) -> TokenResponse:
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.jwt_access_token_minutes)
    token = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + lifetime},
        key,
        algorithm="HS256",
    )
    return TokenResponse(access_token=token, expires_in=int(lifetime.total_seconds()))


def create_refresh_session(user_id: int, session: AsyncSession) -> RefreshSession:
    refresh_session = RefreshSession(
        jti=uuid4(),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc).replace(microsecond=0)
        + timedelta(days=settings.jwt_refresh_token_days),
    )
    session.add(refresh_session)
    return refresh_session


def create_refresh_token(refresh_session: RefreshSession, key: str) -> str:
    return jwt.encode(
        {
            "sub": str(refresh_session.user_id),
            "jti": str(refresh_session.jti),
            "iat": datetime.now(timezone.utc),
            "exp": refresh_session.expires_at,
            "token_type": "refresh",
        },
        key,
        algorithm="HS256",
    )
