"""Tests for role-based access control (RBAC)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from duh.api.rbac import (
    ROLE_HIERARCHY,
    require_admin,
    require_contributor,
    require_role,
    require_viewer,
)

# ── ROLE_HIERARCHY ─────────────────────────────────────────────


class TestRoleHierarchy:
    def test_admin_is_highest(self) -> None:
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["contributor"]
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["viewer"]

    def test_contributor_above_viewer(self) -> None:
        assert ROLE_HIERARCHY["contributor"] > ROLE_HIERARCHY["viewer"]

    def test_all_roles_present(self) -> None:
        assert set(ROLE_HIERARCHY.keys()) == {"admin", "contributor", "viewer"}

    def test_hierarchy_values_ascending(self) -> None:
        assert (
            ROLE_HIERARCHY["viewer"]
            < ROLE_HIERARCHY["contributor"]
            < ROLE_HIERARCHY["admin"]
        )


# ── require_role ───────────────────────────────────────────────


def _make_user(role: str = "contributor") -> SimpleNamespace:
    """Create a fake user object with the given role."""
    return SimpleNamespace(
        id="user-1",
        email="test@example.com",
        display_name="Test",
        role=role,
        is_active=True,
    )


def _build_app(minimum_role: str, user: SimpleNamespace | None = None) -> FastAPI:
    """Build a tiny FastAPI app that uses require_role on a test endpoint.

    Overrides ``get_current_user`` so no real DB/JWT is needed.
    """
    from duh.api.auth import get_current_user

    app = FastAPI()

    dep = require_role(minimum_role)

    @app.get("/protected")
    async def protected(u=Depends(dep)):  # noqa: B008
        return {"role": u.role, "id": u.id}

    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user

    return app


class TestRequireRole:
    """Test the require_role dependency factory via real HTTP calls."""

    # ── admin-level endpoint ──────────────────────────────────

    def test_admin_passes_admin_check(self) -> None:
        app = _build_app("admin", _make_user("admin"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_contributor_fails_admin_check(self) -> None:
        app = _build_app("admin", _make_user("contributor"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    def test_viewer_fails_admin_check(self) -> None:
        app = _build_app("admin", _make_user("viewer"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403

    # ── contributor-level endpoint ────────────────────────────

    def test_admin_passes_contributor_check(self) -> None:
        app = _build_app("contributor", _make_user("admin"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_contributor_passes_contributor_check(self) -> None:
        app = _build_app("contributor", _make_user("contributor"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_viewer_fails_contributor_check(self) -> None:
        app = _build_app("contributor", _make_user("viewer"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "contributor" in resp.json()["detail"].lower()

    # ── viewer-level endpoint ─────────────────────────────────

    def test_admin_passes_viewer_check(self) -> None:
        app = _build_app("viewer", _make_user("admin"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_contributor_passes_viewer_check(self) -> None:
        app = _build_app("viewer", _make_user("contributor"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_viewer_passes_viewer_check(self) -> None:
        app = _build_app("viewer", _make_user("viewer"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    # ── edge cases ────────────────────────────────────────────

    def test_unknown_role_denied(self) -> None:
        """A user with an unrecognised role (level 0) is denied."""
        app = _build_app("viewer", _make_user("unknown_role"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403

    def test_no_role_attr_denied(self) -> None:
        """User object missing 'role' attribute is treated as level 0."""
        user = SimpleNamespace(id="user-1", email="a@b.com")
        app = _build_app("viewer", user)
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403

    def test_unknown_minimum_role_accepts_any(self) -> None:
        """If minimum_role is not in ROLE_HIERARCHY its level defaults to 0.

        Any valid user (viewer=1 > 0) should pass.
        """
        app = _build_app("nonexistent", _make_user("viewer"))
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200


# ── convenience aliases ────────────────────────────────────────


class TestConvenienceAliases:
    """Verify pre-built require_admin / require_contributor / require_viewer."""

    def test_require_admin_callable(self) -> None:
        assert callable(require_admin)

    def test_require_contributor_callable(self) -> None:
        assert callable(require_contributor)

    def test_require_viewer_callable(self) -> None:
        assert callable(require_viewer)

    def _build_alias_app(self, dep: object, user: SimpleNamespace) -> FastAPI:
        from duh.api.auth import get_current_user

        app = FastAPI()

        @app.get("/test")
        async def endpoint(u=Depends(dep)):  # noqa: B008
            return {"ok": True}

        app.dependency_overrides[get_current_user] = lambda: user
        return app

    def test_require_admin_blocks_contributor(self) -> None:
        app = self._build_alias_app(require_admin, _make_user("contributor"))
        resp = TestClient(app).get("/test")
        assert resp.status_code == 403

    def test_require_admin_passes_admin(self) -> None:
        app = self._build_alias_app(require_admin, _make_user("admin"))
        resp = TestClient(app).get("/test")
        assert resp.status_code == 200

    def test_require_contributor_passes_contributor(self) -> None:
        app = self._build_alias_app(require_contributor, _make_user("contributor"))
        resp = TestClient(app).get("/test")
        assert resp.status_code == 200

    def test_require_viewer_passes_viewer(self) -> None:
        app = self._build_alias_app(require_viewer, _make_user("viewer"))
        resp = TestClient(app).get("/test")
        assert resp.status_code == 200

    def test_require_viewer_blocks_unknown(self) -> None:
        app = self._build_alias_app(require_viewer, _make_user("guest"))
        resp = TestClient(app).get("/test")
        assert resp.status_code == 403
