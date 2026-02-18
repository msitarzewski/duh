"""Multi-user integration tests for v0.5 user accounts, JWT auth, and RBAC.

Tests:
- User isolation: threads are scoped to their owner at the data layer
- Admin sees all: admin user can see threads from all users
- Registration flow: register -> login -> /me
- Role enforcement: viewer < contributor < admin
- Per-user rate limiting: independent limits per JWT identity
- JWT token validation: expired, invalid, missing tokens rejected
- User deactivation: deactivated user's JWT is rejected
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.auth import create_token, hash_password
from duh.api.auth import router as auth_router
from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.api.rbac import require_admin, require_contributor, require_viewer
from duh.memory.models import Base, Thread, User

# ── Helpers ────────────────────────────────────────────────────


async def _make_multi_user_app(
    *,
    jwt_secret: str = "test-secret-key-32chars-long!!!!",
    registration_enabled: bool = True,
    token_expiry_hours: int = 24,
    rate_limit: int = 100,
    rate_limit_window: int = 60,
) -> FastAPI:
    """Create a FastAPI app with auth, RBAC endpoints, and in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="test-multi-user")
    app.state.config = SimpleNamespace(
        auth=SimpleNamespace(
            jwt_secret=jwt_secret,
            registration_enabled=registration_enabled,
            token_expiry_hours=token_expiry_hours,
        ),
        api=SimpleNamespace(
            cors_origins=["http://localhost:3000"],
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    # Add middleware (same order as production)
    app.add_middleware(
        RateLimitMiddleware, rate_limit=rate_limit, window=rate_limit_window
    )
    app.add_middleware(APIKeyMiddleware)

    # Auth routes
    app.include_router(auth_router)

    # RBAC-protected test endpoints
    @app.get("/api/admin-only")
    async def admin_endpoint(
        user=Depends(require_admin),  # noqa: B008
    ) -> dict[str, str]:
        return {"role": user.role, "msg": "admin access granted"}

    @app.get("/api/contributor-only")
    async def contributor_endpoint(
        user=Depends(require_contributor),  # noqa: B008
    ) -> dict[str, str]:
        return {"role": user.role, "msg": "contributor access granted"}

    @app.get("/api/viewer-only")
    async def viewer_endpoint(
        user=Depends(require_viewer),  # noqa: B008
    ) -> dict[str, str]:
        return {"role": user.role, "msg": "viewer access granted"}

    @app.get("/api/test")
    async def test_endpoint() -> dict[str, str]:
        return {"msg": "ok"}

    return app


async def _create_user_in_db(
    app: FastAPI,
    *,
    email: str,
    password: str = "test-password-123",
    display_name: str = "Test User",
    role: str = "contributor",
    is_active: bool = True,
) -> User:
    """Insert a user directly into the DB and return the User object."""
    async with app.state.db_factory() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _create_thread_for_user(app: FastAPI, user_id: str, question: str) -> Thread:
    """Insert a thread directly into the DB, owned by user_id."""
    async with app.state.db_factory() as session:
        thread = Thread(question=question, user_id=user_id)
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        return thread


def _get_token(user_id: str, secret: str = "test-secret-key-32chars-long!!!!") -> str:
    """Create a JWT token for the given user ID."""
    return create_token(user_id, secret)


def _auth_headers(token: str) -> dict[str, str]:
    """Return Authorization header dict for Bearer token."""
    return {"Authorization": f"Bearer {token}"}


# ── 1. User Isolation ─────────────────────────────────────────


class TestUserIsolation:
    """User A's threads are not visible to User B when filtering by user_id."""

    async def test_threads_have_user_id_fk(self) -> None:
        """Threads created with a user_id are linked to that user in the DB."""
        app = await _make_multi_user_app()
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")

        await _create_thread_for_user(app, user_a.id, "Alice's question")
        await _create_thread_for_user(app, user_b.id, "Bob's question")

        async with app.state.db_factory() as session:
            # Query threads filtered by user_a
            stmt = select(Thread).where(Thread.user_id == user_a.id)
            result = await session.execute(stmt)
            alice_threads = list(result.scalars().all())

            assert len(alice_threads) == 1
            assert alice_threads[0].question == "Alice's question"
            assert alice_threads[0].user_id == user_a.id

    async def test_user_b_cannot_see_user_a_threads(self) -> None:
        """Filtering threads by user_id isolates each user's data."""
        app = await _make_multi_user_app()
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")

        await _create_thread_for_user(app, user_a.id, "Alice thread 1")
        await _create_thread_for_user(app, user_a.id, "Alice thread 2")
        await _create_thread_for_user(app, user_b.id, "Bob thread 1")

        async with app.state.db_factory() as session:
            # Bob's filtered view
            stmt = select(Thread).where(Thread.user_id == user_b.id)
            result = await session.execute(stmt)
            bob_threads = list(result.scalars().all())

            assert len(bob_threads) == 1
            assert bob_threads[0].question == "Bob thread 1"

            # Alice's filtered view
            stmt = select(Thread).where(Thread.user_id == user_a.id)
            result = await session.execute(stmt)
            alice_threads = list(result.scalars().all())

            assert len(alice_threads) == 2

    async def test_unowned_threads_have_null_user_id(self) -> None:
        """Threads without a user_id (pre-v0.5 / anonymous) have null user_id."""
        app = await _make_multi_user_app()

        async with app.state.db_factory() as session:
            thread = Thread(question="Anonymous question")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

        assert thread.user_id is None


# ── 2. Admin Sees All ─────────────────────────────────────────


class TestAdminSeesAll:
    """Admin user can see threads from all users."""

    async def test_admin_can_query_all_threads(self) -> None:
        """Admin's unfiltered query returns threads from all users."""
        app = await _make_multi_user_app()
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")
        admin = await _create_user_in_db(app, email="admin@example.com", role="admin")

        await _create_thread_for_user(app, user_a.id, "Alice thread")
        await _create_thread_for_user(app, user_b.id, "Bob thread")
        await _create_thread_for_user(app, admin.id, "Admin thread")

        async with app.state.db_factory() as session:
            # Admin sees all (no user_id filter)
            stmt = select(Thread)
            result = await session.execute(stmt)
            all_threads = list(result.scalars().all())
            assert len(all_threads) == 3

    async def test_admin_can_see_specific_user_threads(self) -> None:
        """Admin can filter to see a specific user's threads."""
        app = await _make_multi_user_app()
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")

        await _create_thread_for_user(app, user_a.id, "Alice thread")
        await _create_thread_for_user(app, user_b.id, "Bob thread")

        async with app.state.db_factory() as session:
            # Admin can look at Bob's threads specifically
            stmt = select(Thread).where(Thread.user_id == user_b.id)
            result = await session.execute(stmt)
            bob_threads = list(result.scalars().all())
            assert len(bob_threads) == 1
            assert bob_threads[0].question == "Bob thread"


# ── 3. Registration Flow ─────────────────────────────────────


class TestRegistrationFlow:
    """Full registration -> login -> /me flow."""

    async def test_register_login_me(self) -> None:
        """Register a new user, login, and access /me with the token."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Step 1: Register
        reg_resp = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "secure-password-123",
                "display_name": "New User",
            },
        )
        assert reg_resp.status_code == 200
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        assert reg_data["token_type"] == "bearer"
        assert reg_data["role"] == "contributor"

        # Step 2: Login with same credentials
        login_resp = client.post(
            "/api/auth/login",
            json={
                "email": "newuser@example.com",
                "password": "secure-password-123",
            },
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert "access_token" in login_data
        login_token = login_data["access_token"]

        # Step 3: Access /me with the login token
        me_resp = client.get(
            "/api/auth/me",
            headers=_auth_headers(login_token),
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == "newuser@example.com"
        assert me_data["display_name"] == "New User"
        assert me_data["role"] == "contributor"
        assert me_data["is_active"] is True

    async def test_register_returns_valid_jwt(self) -> None:
        """Token from registration can be used immediately for /me."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        reg_resp = client.post(
            "/api/auth/register",
            json={
                "email": "immediate@example.com",
                "password": "password123",
                "display_name": "Immediate User",
            },
        )
        assert reg_resp.status_code == 200
        token = reg_resp.json()["access_token"]

        # Use registration token directly (no login needed)
        me_resp = client.get(
            "/api/auth/me",
            headers=_auth_headers(token),
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "immediate@example.com"

    async def test_two_users_register_independently(self) -> None:
        """Two different users can register and access their own /me."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Register user 1
        resp1 = client.post(
            "/api/auth/register",
            json={
                "email": "user1@example.com",
                "password": "pass1",
                "display_name": "User One",
            },
        )
        assert resp1.status_code == 200
        token1 = resp1.json()["access_token"]

        # Register user 2
        resp2 = client.post(
            "/api/auth/register",
            json={
                "email": "user2@example.com",
                "password": "pass2",
                "display_name": "User Two",
            },
        )
        assert resp2.status_code == 200
        token2 = resp2.json()["access_token"]

        # Each user sees their own info
        me1 = client.get("/api/auth/me", headers=_auth_headers(token1))
        assert me1.json()["email"] == "user1@example.com"

        me2 = client.get("/api/auth/me", headers=_auth_headers(token2))
        assert me2.json()["email"] == "user2@example.com"


# ── 4. Role Enforcement ──────────────────────────────────────


class TestRoleEnforcement:
    """Viewer cannot perform contributor actions; contributor cannot admin."""

    async def test_viewer_cannot_access_contributor_endpoint(self) -> None:
        """Viewer role is denied at contributor-level endpoints."""
        app = await _make_multi_user_app()
        viewer = await _create_user_in_db(
            app, email="viewer@example.com", role="viewer"
        )
        token = _get_token(viewer.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/contributor-only", headers=_auth_headers(token))
        assert resp.status_code == 403
        assert "contributor" in resp.json()["detail"].lower()

    async def test_viewer_cannot_access_admin_endpoint(self) -> None:
        """Viewer role is denied at admin-level endpoints."""
        app = await _make_multi_user_app()
        viewer = await _create_user_in_db(
            app, email="viewer@example.com", role="viewer"
        )
        token = _get_token(viewer.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/admin-only", headers=_auth_headers(token))
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    async def test_contributor_cannot_access_admin_endpoint(self) -> None:
        """Contributor role is denied at admin-level endpoints."""
        app = await _make_multi_user_app()
        contrib = await _create_user_in_db(
            app, email="contrib@example.com", role="contributor"
        )
        token = _get_token(contrib.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/admin-only", headers=_auth_headers(token))
        assert resp.status_code == 403

    async def test_contributor_can_access_contributor_endpoint(self) -> None:
        """Contributor role passes contributor-level check."""
        app = await _make_multi_user_app()
        contrib = await _create_user_in_db(
            app, email="contrib@example.com", role="contributor"
        )
        token = _get_token(contrib.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/contributor-only", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "contributor"

    async def test_admin_can_access_all_endpoints(self) -> None:
        """Admin role passes all role checks."""
        app = await _make_multi_user_app()
        admin = await _create_user_in_db(app, email="admin@example.com", role="admin")
        token = _get_token(admin.id)
        client = TestClient(app, raise_server_exceptions=False)

        # Admin can access admin-only
        resp = client.get("/api/admin-only", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

        # Admin can access contributor-only
        resp = client.get("/api/contributor-only", headers=_auth_headers(token))
        assert resp.status_code == 200

        # Admin can access viewer-only
        resp = client.get("/api/viewer-only", headers=_auth_headers(token))
        assert resp.status_code == 200

    async def test_viewer_can_access_viewer_endpoint(self) -> None:
        """Viewer role passes viewer-level check."""
        app = await _make_multi_user_app()
        viewer = await _create_user_in_db(
            app, email="viewer@example.com", role="viewer"
        )
        token = _get_token(viewer.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/viewer-only", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"


# ── 5. Per-User Rate Limiting ─────────────────────────────────


class TestPerUserRateLimiting:
    """User A hitting rate limit doesn't affect User B."""

    async def test_user_a_rate_limit_does_not_affect_user_b(self) -> None:
        """Each user has independent rate limit counters."""
        app = await _make_multi_user_app(rate_limit=3, rate_limit_window=60)
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")

        token_a = _get_token(user_a.id)
        token_b = _get_token(user_b.id)
        client = TestClient(app, raise_server_exceptions=False)

        # User A exhausts their rate limit
        for _ in range(3):
            resp = client.get("/api/test", headers=_auth_headers(token_a))
            assert resp.status_code == 200

        # User A is now rate limited
        resp = client.get("/api/test", headers=_auth_headers(token_a))
        assert resp.status_code == 429

        # User B is unaffected
        resp = client.get("/api/test", headers=_auth_headers(token_b))
        assert resp.status_code == 200

    async def test_rate_limit_headers_show_user_identity(self) -> None:
        """Rate limit response headers identify the user."""
        app = await _make_multi_user_app(rate_limit=10, rate_limit_window=60)
        user = await _create_user_in_db(app, email="alice@example.com")

        token = _get_token(user.id)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        assert resp.headers["X-RateLimit-Key"] == f"user:{user.id}"

    async def test_rate_limit_remaining_decrements_per_user(self) -> None:
        """Remaining count decrements independently per user."""
        app = await _make_multi_user_app(rate_limit=5, rate_limit_window=60)
        user_a = await _create_user_in_db(app, email="alice@example.com")
        user_b = await _create_user_in_db(app, email="bob@example.com")

        token_a = _get_token(user_a.id)
        token_b = _get_token(user_b.id)
        client = TestClient(app, raise_server_exceptions=False)

        # User A makes 3 requests
        for _ in range(3):
            client.get("/api/test", headers=_auth_headers(token_a))

        # User A should have 2 remaining
        resp_a = client.get("/api/test", headers=_auth_headers(token_a))
        assert resp_a.headers["X-RateLimit-Remaining"] == "1"

        # User B should still have 4 remaining (first request)
        resp_b = client.get("/api/test", headers=_auth_headers(token_b))
        assert resp_b.headers["X-RateLimit-Remaining"] == "4"


# ── 6. JWT Token Validation ──────────────────────────────────


class TestJWTTokenValidation:
    """Expired, invalid, and missing tokens are rejected."""

    async def test_expired_token_rejected(self) -> None:
        """An expired JWT is rejected with 401."""
        app = await _make_multi_user_app()
        user = await _create_user_in_db(app, email="expired@example.com")
        client = TestClient(app, raise_server_exceptions=False)

        # Create a token that expired in the past
        payload = {
            "sub": user.id,
            "exp": time.time() - 3600,  # 1 hour ago
            "iat": time.time() - 7200,
        }
        expired_token = jwt.encode(
            payload, "test-secret-key-32chars-long!!!!", algorithm="HS256"
        )

        resp = client.get(
            "/api/auth/me",
            headers=_auth_headers(expired_token),
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    async def test_invalid_token_rejected(self) -> None:
        """A garbled JWT string is rejected with 401."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/auth/me",
            headers=_auth_headers("not-a-valid-jwt-token"),
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    async def test_wrong_secret_token_rejected(self) -> None:
        """A JWT signed with the wrong secret is rejected."""
        app = await _make_multi_user_app()
        user = await _create_user_in_db(app, email="wrong@example.com")
        client = TestClient(app, raise_server_exceptions=False)

        # Sign with a different secret
        bad_token = create_token(user.id, "wrong-secret-key-32chars-long!!")

        resp = client.get(
            "/api/auth/me",
            headers=_auth_headers(bad_token),
        )
        assert resp.status_code == 401

    async def test_missing_token_rejected(self) -> None:
        """Request without Authorization header is rejected with 401."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_malformed_auth_header_rejected(self) -> None:
        """Authorization header without 'Bearer ' prefix is rejected."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Token some-token-value"},
        )
        assert resp.status_code == 401

    async def test_token_for_nonexistent_user_rejected(self) -> None:
        """A valid JWT for a user_id that doesn't exist in the DB is rejected."""
        app = await _make_multi_user_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Create a token for a user that doesn't exist
        token = _get_token("nonexistent-user-id-000")

        resp = client.get(
            "/api/auth/me",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 401
        assert "not found" in resp.json()["detail"].lower()


# ── 7. User Deactivation ─────────────────────────────────────


class TestUserDeactivation:
    """Deactivated user's JWT is rejected even if the token itself is valid."""

    async def test_deactivated_user_rejected_at_me(self) -> None:
        """A deactivated user cannot access /me even with a valid JWT."""
        app = await _make_multi_user_app()
        user = await _create_user_in_db(
            app, email="deactivated@example.com", is_active=True
        )
        token = _get_token(user.id)
        client = TestClient(app, raise_server_exceptions=False)

        # Verify user can access /me while active
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 200

        # Deactivate the user in the DB
        async with app.state.db_factory() as session:
            stmt = select(User).where(User.id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one()
            db_user.is_active = False
            await session.commit()

        # Same token should now be rejected
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 401
        assert "not found or inactive" in resp.json()["detail"].lower()

    async def test_deactivated_user_cannot_login(self) -> None:
        """A deactivated user cannot login even with correct credentials."""
        app = await _make_multi_user_app()
        await _create_user_in_db(
            app, email="disabled@example.com", password="mypass", is_active=False
        )
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/auth/login",
            json={"email": "disabled@example.com", "password": "mypass"},
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()

    async def test_deactivated_user_rejected_at_rbac_endpoint(self) -> None:
        """A deactivated user cannot access RBAC-protected endpoints."""
        app = await _make_multi_user_app()
        user = await _create_user_in_db(
            app, email="deact-rbac@example.com", role="admin", is_active=True
        )
        token = _get_token(user.id)
        client = TestClient(app, raise_server_exceptions=False)

        # Verify access works while active
        resp = client.get("/api/admin-only", headers=_auth_headers(token))
        assert resp.status_code == 200

        # Deactivate
        async with app.state.db_factory() as session:
            stmt = select(User).where(User.id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one()
            db_user.is_active = False
            await session.commit()

        # Now admin endpoint should reject
        resp = client.get("/api/admin-only", headers=_auth_headers(token))
        assert resp.status_code == 401
