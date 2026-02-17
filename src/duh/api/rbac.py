"""Role-based access control for the duh API.

Roles: admin > contributor > viewer.
Use ``require_role`` to create a FastAPI dependency that checks the
authenticated user has at least the given role level.

Example::

    @router.get("/admin-only")
    async def admin_endpoint(user=Depends(require_role("admin"))):
        ...
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException

from duh.api.auth import get_current_user

# Role hierarchy: higher number = more privileges.
ROLE_HIERARCHY: dict[str, int] = {"admin": 3, "contributor": 2, "viewer": 1}


def require_role(minimum_role: str):
    """FastAPI dependency factory: require user has at least *minimum_role*.

    Args:
        minimum_role: One of ``"admin"``, ``"contributor"``, ``"viewer"``.

    Returns:
        An async FastAPI dependency callable that resolves to the
        authenticated ``User`` if the role check passes.

    Raises:
        HTTPException 401: If no authenticated user is present.
        HTTPException 403: If the user's role is below the minimum.
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check_role(
        user: Any = Depends(get_current_user),  # noqa: B008
    ) -> Any:
        user_level = ROLE_HIERARCHY.get(getattr(user, "role", ""), 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {minimum_role} role",
            )
        return user

    return _check_role


# Convenience pre-built dependencies.
require_admin = require_role("admin")
require_contributor = require_role("contributor")
require_viewer = require_role("viewer")
