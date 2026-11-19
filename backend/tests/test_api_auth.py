from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import jwt
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.refresh_sessions import RefreshSession

# Apply the asyncio marker to all tests in this module.
pytestmark = pytest.mark.asyncio

CREDENTIALS = {"username": "alice", "password": "correct-password"}
ORDER = {
    "user_id": 1,
    "symbol": "BTC-USD",
    "side": "BUY",
    "type": "LIMIT",
    "price": "100.00",
    "quantity": "2",
}


@pytest_asyncio.fixture
async def auth_headers(rest_client: httpx.AsyncClient) -> dict[str, str]:
    registration = await rest_client.post("/api/auth/register", json=CREDENTIALS)
    assert registration.status_code == 201
    response = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_register_returns_user_without_credentials(
    rest_client: httpx.AsyncClient,
):
    response = await rest_client.post("/api/auth/register", json=CREDENTIALS)

    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice"}


async def test_register_duplicate_username_returns_conflict(
    rest_client: httpx.AsyncClient,
):
    await rest_client.post("/api/auth/register", json=CREDENTIALS)
    response = await rest_client.post("/api/auth/register", json=CREDENTIALS)

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}
    login = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    other = await rest_client.post(
        "/api/auth/register", json={**CREDENTIALS, "username": "bob"}
    )
    assert other.status_code == 201


@pytest.mark.parametrize("endpoint", ["register", "login"])
@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "ab", "password": "correct-password"},
        {"username": "invalid username", "password": "correct-password"},
        {"username": "alice", "password": "short"},
        {"username": "alice"},
        {"password": "correct-password"},
    ],
)
async def test_invalid_credentials_body_returns_validation_error(
    rest_client: httpx.AsyncClient, endpoint: str, credentials: dict
):
    response = await rest_client.post(f"/api/auth/{endpoint}", json=credentials)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


async def test_login_returns_valid_access_token(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    response = await rest_client.post("/api/auth/login", json=CREDENTIALS)

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"access_token", "token_type", "expires_in"}
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    claims = jwt.decode(
        data["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    assert claims["sub"] == "1"
    assert claims["exp"] - claims["iat"] == data["expires_in"]
    assert "password" not in claims
    book = await rest_client.get(
        "/api/order_book/BTC-USD",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert book.status_code == 200


@pytest.mark.parametrize(
    "credentials",
    [
        {**CREDENTIALS, "password": "wrong-password"},
        {**CREDENTIALS, "username": "unknown-user"},
    ],
)
async def test_login_invalid_credentials_returns_unauthorized(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str], credentials: dict
):
    response = await rest_client.post("/api/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid credentials or expired token"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/orders", ORDER),
        ("GET", "/api/orders/1", None),
        ("POST", "/api/orders/1/cancel", None),
    ],
)
@pytest.mark.parametrize("authorization", [None, "Basic credentials", "Bearer"])
async def test_protected_routes_require_bearer_token(
    rest_client: httpx.AsyncClient,
    method: str,
    path: str,
    body: dict | None,
    authorization: str | None,
):
    headers = {"Authorization": authorization} if authorization else {}
    response = await rest_client.request(method, path, json=body, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid credentials or expired token"}


@pytest.mark.parametrize(
    "token_case",
    [
        "malformed",
        "signature",
        "expired",
        "missing_exp",
        "missing_sub",
        "missing_iat",
        "future_iat",
        "invalid_sub",
        "numeric_sub",
        "unknown_user",
        "algorithm",
    ],
)
async def test_invalid_access_token_returns_unauthorized(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str], token_case: str
):
    now = datetime.now(timezone.utc)
    claims = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=15)}
    key = settings.jwt_secret_key.get_secret_value()
    algorithm = "HS256"
    if token_case.startswith("missing_"):
        claims.pop(token_case.removeprefix("missing_"))
    elif token_case == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif token_case == "future_iat":
        claims["iat"] = now + timedelta(minutes=5)
    elif token_case == "invalid_sub":
        claims["sub"] = "not-an-id"
    elif token_case == "numeric_sub":
        claims["sub"] = 1
    elif token_case == "unknown_user":
        claims["sub"] = "999"
    elif token_case == "signature":
        key = "another-signing-key-" * 4
    elif token_case == "algorithm":
        algorithm = "HS384"
    token = (
        "not-a-jwt"
        if token_case == "malformed"
        else jwt.encode(claims, key, algorithm=algorithm)
    )
    response = await rest_client.get(
        "/api/orders/1", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid credentials or expired token"}


async def test_missing_signing_key_returns_service_unavailable(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "jwt_secret_key", None)

    login = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    book = await rest_client.get("/api/orders/1", headers=auth_headers)

    for response in (login, book):
        assert response.status_code == 503
        assert response.json() == {"detail": "JWT_SECRET_KEY is not configured"}


async def test_cannot_place_order_for_another_user(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    response = await rest_client.post(
        "/api/orders", json={**ORDER, "user_id": 2}, headers=auth_headers
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cannot place an order for another user"}
    book = await rest_client.get("/api/order_book/BTC-USD", headers=auth_headers)
    assert book.json() == {"symbol": "BTC-USD", "asks": [], "bids": []}


async def test_cannot_read_or_cancel_another_users_order(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    created = await rest_client.post("/api/orders", json=ORDER, headers=auth_headers)
    assert created.status_code == 201
    order_id = created.json()["id"]
    credentials = {"username": "bob", "password": "another-password"}
    registration = await rest_client.post("/api/auth/register", json=credentials)
    assert registration.status_code == 201
    login = await rest_client.post("/api/auth/login", json=credentials)
    assert login.status_code == 200
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    read = await rest_client.get(f"/api/orders/{order_id}", headers=other_headers)
    cancel = await rest_client.post(
        f"/api/orders/{order_id}/cancel", headers=other_headers
    )

    for response in (read, cancel):
        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}
    original = await rest_client.get(f"/api/orders/{order_id}", headers=auth_headers)
    assert original.status_code == 200
    assert original.json()["status"] == "OPEN"


async def test_login_sets_httponly_session_cookies(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    response = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 3
    assert all(
        "HttpOnly" in cookie and "SameSite=strict" in cookie for cookie in cookies
    )
    assert any("Path=/ws" in cookie for cookie in cookies)
    assert any("Path=/api/auth;" in cookie for cookie in cookies)


async def test_refresh_restores_session_after_access_token_expires(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(minutes=20),
            "exp": now - timedelta(seconds=1),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    denied = await rest_client.get(
        "/api/orders/1", headers={"Authorization": f"Bearer {expired}"}
    )
    assert denied.status_code == 401
    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 200
    book = await rest_client.get(
        "/api/order_book/BTC-USD",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert book.status_code == 200
    assert any(
        "access_token=" in cookie for cookie in response.headers.get_list("set-cookie")
    )


@pytest.mark.parametrize("origin", [None, "null", "http://evil.example"])
async def test_refresh_rejects_untrusted_origin(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str], origin: str | None
):
    headers = {"Origin": origin} if origin is not None else {}
    response = await rest_client.post("/api/auth/refresh", headers=headers)
    assert response.status_code == 403


async def test_refresh_requires_refresh_cookie(rest_client: httpx.AsyncClient):
    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 401


async def test_access_token_cannot_refresh_session(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    rest_client.cookies.clear()
    rest_client.cookies.set(
        "refresh_token", auth_headers["Authorization"].removeprefix("Bearer ")
    )
    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 401


async def test_expired_refresh_token_is_rejected(rest_client: httpx.AsyncClient):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(days=8),
            "exp": now - timedelta(days=1),
            "token_type": "refresh",
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    rest_client.cookies.set("refresh_token", token, path="/api/auth/refresh")
    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 401


async def test_order_book_is_public(rest_client: httpx.AsyncClient):
    response = await rest_client.get("/api/order_book/BTC-USD")
    assert response.status_code == 200
    assert response.json() == {"symbol": "BTC-USD", "asks": [], "bids": []}


async def test_logout_clears_session_cookies(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    assert rest_client.cookies.get("access_token")
    assert rest_client.cookies.get("refresh_token")

    response = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )

    assert response.status_code == 204
    assert response.content == b""
    assert rest_client.cookies.get("access_token") is None
    assert rest_client.cookies.get("refresh_token") is None
    refresh = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert refresh.status_code == 401
    repeated = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert repeated.status_code == 204


@pytest.mark.parametrize("origin", [None, "http://evil.example"])
async def test_logout_rejects_untrusted_origin(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str], origin: str | None
):
    headers = {"Origin": origin} if origin is not None else {}
    response = await rest_client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 403
    assert rest_client.cookies.get("refresh_token")


async def test_each_login_persists_a_separate_refresh_session(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    db_sessionmaker: async_sessionmaker[AsyncSession],
):
    first_token = rest_client.cookies.get("refresh_token")
    response = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    assert response.status_code == 200
    second_token = rest_client.cookies.get("refresh_token")
    assert first_token != second_token

    claims = [
        jwt.decode(
            token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"]
        )
        for token in (first_token, second_token)
    ]
    assert claims[0]["jti"] != claims[1]["jti"]
    async with db_sessionmaker() as session:
        for payload in claims:
            stored = await session.get(RefreshSession, UUID(payload["jti"]))
            assert stored is not None
            assert stored.user_id == int(payload["sub"]) == 1
            assert (
                stored.expires_at.replace(tzinfo=timezone.utc).timestamp()
                == payload["exp"]
            )
            assert stored.revoked is False
            assert payload["token_type"] == "refresh"


async def test_failed_login_does_not_create_refresh_session(
    rest_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker[AsyncSession],
):
    registration = await rest_client.post("/api/auth/register", json=CREDENTIALS)
    assert registration.status_code == 201
    response = await rest_client.post(
        "/api/auth/login", json={**CREDENTIALS, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert rest_client.cookies.get("refresh_token") is None
    async with db_sessionmaker() as session:
        assert (await session.scalars(select(RefreshSession))).all() == []


@pytest.mark.parametrize(
    "session_state", ["missing", "revoked", "expired", "wrong_owner"]
)
async def test_refresh_rejects_invalid_session(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    db_sessionmaker: async_sessionmaker[AsyncSession],
    session_state: str,
):
    token = rest_client.cookies.get("refresh_token")
    claims = jwt.decode(
        token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"]
    )
    other_user_id = None
    if session_state == "wrong_owner":
        registration = await rest_client.post(
            "/api/auth/register", json={**CREDENTIALS, "username": "bob"}
        )
        assert registration.status_code == 201
        other_user_id = registration.json()["id"]

    async with db_sessionmaker() as session:
        stored = await session.get(RefreshSession, UUID(claims["jti"]))
        if session_state == "missing":
            await session.delete(stored)
        elif session_state == "revoked":
            stored.revoked = True
        elif session_state == "expired":
            stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        else:
            stored.user_id = other_user_id
        await session.commit()

    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid credentials or expired token"}
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "jti", [None, "invalid-uuid", "00000000-0000-0000-0000-000000000000", 123]
)
async def test_refresh_requires_registered_session_identifier(
    rest_client: httpx.AsyncClient, auth_headers: dict[str, str], jti: str | int | None
):
    claims = jwt.decode(
        rest_client.cookies.get("refresh_token"),
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    if jti is None:
        claims.pop("jti")
    else:
        claims["jti"] = jti
    token = jwt.encode(
        claims, settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )
    rest_client.cookies.clear()
    rest_client.cookies.set("refresh_token", token, path="/api/auth/refresh")

    response = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials or expired token"}
    assert "set-cookie" not in response.headers


async def test_logout_revokes_saved_refresh_token(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    db_sessionmaker: async_sessionmaker[AsyncSession],
):
    saved_token = rest_client.cookies.get("refresh_token")
    claims = jwt.decode(
        saved_token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"]
    )
    logout = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert logout.status_code == 204
    async with db_sessionmaker() as session:
        stored = await session.get(RefreshSession, UUID(claims["jti"]))
        assert stored.revoked is True

    rest_client.cookies.set("refresh_token", saved_token, path="/api/auth")
    repeated_logout = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert repeated_logout.status_code == 204
    rest_client.cookies.clear()
    rest_client.cookies.set("refresh_token", saved_token, path="/api/auth")
    replay = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert replay.status_code == 401
    assert "set-cookie" not in replay.headers


async def test_logout_preserves_another_session_of_same_user(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    first_token = rest_client.cookies.get("refresh_token")
    login = await rest_client.post("/api/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    second_token = rest_client.cookies.get("refresh_token")
    assert first_token != second_token
    logout = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert logout.status_code == 204

    rest_client.cookies.set("refresh_token", first_token, path="/api/auth")
    first_session = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert first_session.status_code == 200
    rest_client.cookies.clear()
    rest_client.cookies.set("refresh_token", second_token, path="/api/auth")
    second_session = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert second_session.status_code == 401


@pytest.mark.parametrize(
    "token_case",
    ["missing", "malformed", "expired", "missing_jti", "unknown_jti", "access"],
)
async def test_logout_accepts_missing_or_invalid_refresh_token(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    token_case: str,
):
    claims = jwt.decode(
        rest_client.cookies.get("refresh_token"),
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    if token_case == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif token_case == "missing_jti":
        claims.pop("jti")
    elif token_case == "unknown_jti":
        claims["jti"] = "00000000-0000-0000-0000-000000000000"
    token = jwt.encode(
        claims, settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )
    if token_case == "malformed":
        token = "not-a-token"
    elif token_case == "access":
        token = auth_headers["Authorization"].removeprefix("Bearer ")
    domain = next(
        cookie.domain
        for cookie in rest_client.cookies.jar
        if cookie.name == "refresh_token"
    )
    rest_client.cookies.clear()
    if token_case != "missing":
        rest_client.cookies.set("refresh_token", token, domain=domain, path="/api/auth")
    response = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 204
    assert not rest_client.cookies


async def test_refresh_migrates_legacy_cookie_path(
    rest_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    saved_token = rest_client.cookies.get("refresh_token")
    domain = next(
        cookie.domain
        for cookie in rest_client.cookies.jar
        if cookie.name == "refresh_token"
    )
    rest_client.cookies.clear()
    rest_client.cookies.set(
        "refresh_token", saved_token, domain=domain, path="/api/auth/refresh"
    )
    refreshed = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert refreshed.status_code == 200
    refresh_cookies = [
        cookie for cookie in rest_client.cookies.jar if cookie.name == "refresh_token"
    ]
    assert len(refresh_cookies) == 1
    assert refresh_cookies[0].path == "/api/auth"
    assert refresh_cookies[0].value == saved_token
    logout = await rest_client.post(
        "/api/auth/logout", headers={"Origin": "http://localhost:8000"}
    )
    assert logout.status_code == 204
    rest_client.cookies.set("refresh_token", saved_token, path="/api/auth")
    replay = await rest_client.post(
        "/api/auth/refresh", headers={"Origin": "http://localhost:8000"}
    )
    assert replay.status_code == 401
