"""JWT authentication for the duh API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# --- Password hashing ---


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# --- JWT ---


def create_token(user_id: str, secret: str, expiry_hours: int = 24) -> str:
    """Create a JWT token."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(hours=expiry_hours),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(status_code=401, detail="Token expired") from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(status_code=401, detail="Invalid token") from err


# --- Request models ---


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool


# --- Dependency: get current user from JWT ---


async def get_current_user(request: Request) -> Any:
    """FastAPI dependency: extract user from JWT Bearer token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )

    token = auth_header.split(" ", 1)[1]
    config = request.app.state.config
    payload = decode_token(token, config.auth.jwt_secret)
    user_id = payload.get("sub")

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        stmt = select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


# --- Endpoints ---


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, request: Request) -> TokenResponse:
    """Register a new user."""
    config = request.app.state.config
    if not config.auth.registration_enabled:
        raise HTTPException(status_code=403, detail="Registration is disabled")

    if not config.auth.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        # Check email uniqueness
        stmt = select(User).where(User.email == body.email)
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_token(
        user.id, config.auth.jwt_secret, config.auth.token_expiry_hours
    )
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate and get token."""
    config = request.app.state.config
    if not config.auth.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        stmt = select(User).where(User.email == body.email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_token(
        user.id, config.auth.jwt_secret, config.auth.token_expiry_hours
    )
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.get("/me", response_model=UserResponse)
async def me(user: Any = Depends(get_current_user)) -> UserResponse:  # noqa: B008
    """Get current user info."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )
