"""JWT authentication for the duh API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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

    if (
        user is None
        or user.password_hash is None
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_token(
        user.id, config.auth.jwt_secret, config.auth.token_expiry_hours
    )
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


class GuestRequest(BaseModel):
    email: str


@router.post("/guest", response_model=TokenResponse)
async def guest_login(body: GuestRequest, request: Request) -> TokenResponse:
    """Create or retrieve a guest user (email-only, no password)."""
    config = request.app.state.config
    if not config.auth.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        stmt = select(User).where(User.email == body.email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            if not existing.is_guest:
                raise HTTPException(
                    status_code=409,
                    detail="Email registered as full account. Please log in.",
                )
            # Return token for existing guest
            token = create_token(existing.id, config.auth.jwt_secret, expiry_hours=4)
            return TokenResponse(
                access_token=token, user_id=existing.id, role=existing.role
            )

        # Create new guest user
        user = User(
            email=body.email,
            display_name=body.email.split("@")[0],
            is_guest=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_token(user.id, config.auth.jwt_secret, expiry_hours=4)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


class AuthStatusResponse(BaseModel):
    auth_required: bool


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    """Check if authentication is required (dev mode detection)."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)
        keys = await repo.list_api_keys()

    # Auth is required if API keys or users exist
    if keys:
        return AuthStatusResponse(auth_required=True)

    from sqlalchemy import func, select

    from duh.memory.models import User

    async with db_factory() as session:
        count = (await session.execute(select(func.count(User.id)))).scalar() or 0

    return AuthStatusResponse(auth_required=count > 0)


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


# --- Password reset ---


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    message: str


def _create_reset_token(user_id: str, secret: str, expiry_minutes: int) -> str:
    """Create a short-lived JWT for password reset."""
    payload = {
        "sub": user_id,
        "purpose": "password_reset",
        "exp": datetime.now(UTC) + timedelta(minutes=expiry_minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_reset_token(token: str, secret: str) -> str:
    """Decode a reset token and return user_id. Raises HTTPException."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(status_code=400, detail="Reset link has expired") from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(status_code=400, detail="Invalid reset link") from err

    if payload.get("purpose") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid reset link")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid reset link")
    return user_id


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    body: ForgotPasswordRequest, request: Request
) -> ForgotPasswordResponse:
    """Request a password reset email."""
    config = request.app.state.config
    generic_msg = "If that email is registered, you will receive a reset link."

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        stmt = select(User).where(
            User.email == body.email,
            User.is_active == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None:
        # Don't reveal whether the email exists
        return ForgotPasswordResponse(message=generic_msg)

    token = _create_reset_token(
        user.id,
        config.auth.jwt_secret,
        config.auth.reset_token_expiry_minutes,
    )

    # Build reset URL
    origin = (
        request.headers.get("origin")
        or request.headers.get("referer", "").rstrip("/")
        or f"http://{config.api.host}:{config.api.port}"
    )
    reset_url = f"{origin}/reset-password?token={token}"

    # Send email
    try:
        from duh.mail import send_email

        send_email(
            config.mail,
            to=user.email,
            subject="Reset your duh password",
            body_html=(
                f"<p>Hi {user.display_name},</p>"
                f"<p>Click the link below to reset your password. "
                f"This link expires in "
                f"{config.auth.reset_token_expiry_minutes} minutes.</p>"
                f'<p><a href="{reset_url}">{reset_url}</a></p>'
                f"<p>If you didn't request this, ignore this email.</p>"
            ),
            body_text=(
                f"Hi {user.display_name},\n\n"
                f"Reset your password:\n{reset_url}\n\n"
                f"This link expires in "
                f"{config.auth.reset_token_expiry_minutes} minutes.\n\n"
                f"If you didn't request this, ignore this email."
            ),
        )
    except Exception as exc:
        logger.exception("Failed to send password reset email to %s", user.email)
        raise HTTPException(
            status_code=503,
            detail="Unable to send email. Check mail configuration.",
        ) from exc

    return ForgotPasswordResponse(message=generic_msg)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest, request: Request
) -> ResetPasswordResponse:
    """Reset password using a token from the reset email."""
    config = request.app.state.config
    user_id = _decode_reset_token(body.token, config.auth.jwt_secret)

    from sqlalchemy import select

    from duh.memory.models import User

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        stmt = select(User).where(
            User.id == user_id,
            User.is_active == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=400, detail="Invalid reset link")

        user.password_hash = hash_password(body.new_password)
        await session.commit()

    return ResetPasswordResponse(
        message="Password has been reset. You can now sign in."
    )
