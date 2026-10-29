"""JWT authentication for the duh API."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from starlette.requests import HTTPConnection  # noqa: TC002 -- FastAPI annotations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# --- Password hashing ---


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    _validate_new_password(password)
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    # bcrypt before v5 truncated at 72 bytes. Keep those accounts usable.
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def _validate_new_password(password: str) -> str:
    """Validate bcrypt's byte limit without truncating new credentials."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return password


# --- JWT ---


def create_token(user_id: str, secret: str, expiry_hours: int = 24) -> str:
    """Create a JWT token."""
    payload = {
        "sub": user_id,
        "purpose": "access",
        "exp": datetime.now(UTC) + timedelta(hours=expiry_hours),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
        # Existing access tokens had no purpose claim; reset tokens always do.
        if payload.get("purpose", "access") != "access" or not payload["sub"]:
            raise jwt.InvalidTokenError("Invalid access token")
        return payload
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(status_code=401, detail="Token expired") from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(status_code=401, detail="Invalid token") from err


# --- Request models ---


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str

    _validate_password = field_validator("password")(_validate_new_password)


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


async def get_current_user(request: HTTPConnection) -> Any:
    """FastAPI dependency: extract user from JWT Bearer token."""
    auth_header = request.headers.get("Authorization")
    scheme, _, token = (auth_header or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
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


async def authenticate_connection(
    connection: HTTPConnection, *, token: str | None = None, api_key: str | None = None
) -> None:
    """Authenticate HTTP and WebSocket requests with the same local-dev policy."""
    from sqlalchemy import func, select

    from duh.api.middleware import hash_api_key
    from duh.memory.models import User
    from duh.memory.repository import MemoryRepository

    header = connection.headers.get("Authorization")
    if header is not None:
        scheme, _, credential = header.partition(" ")
        if scheme.lower() != "bearer" or not credential:
            raise HTTPException(status_code=401, detail="Invalid Authorization header")
        token = credential
    if token is not None:
        payload = decode_token(token, connection.app.state.config.auth.jwt_secret)
        async with connection.app.state.db_factory() as session:
            user = await session.scalar(
                select(User).where(User.id == payload["sub"], User.is_active.is_(True))
            )
        if user is None:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        connection.state.user_id = user.id
        return

    raw_key = api_key if api_key is not None else connection.headers.get("X-API-Key")
    async with connection.app.state.db_factory() as session:
        repo = MemoryRepository(session)
        if raw_key is not None:
            key = await repo.validate_api_key(hash_api_key(raw_key))
            if key is None:
                raise HTTPException(
                    status_code=401, detail="Invalid or revoked API key."
                )
            connection.state.api_key_id = key.id
            return
        keys = await repo.list_api_keys()
        users = await session.scalar(select(func.count(User.id)))
    if keys or users:
        raise HTTPException(status_code=401, detail="Missing API key or Bearer token.")


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

    _validate_password = field_validator("new_password")(_validate_new_password)


class ResetPasswordResponse(BaseModel):
    message: str


def _create_reset_token(
    user_id: str, secret: str, expiry_minutes: int, *, password_hash: str | None
) -> str:
    """Create a short-lived JWT for password reset."""
    payload = {
        "sub": user_id,
        "purpose": "password_reset",
        "password_version": _password_version(password_hash, secret),
        "exp": datetime.now(UTC) + timedelta(minutes=expiry_minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_reset_token(token: str, secret: str) -> dict[str, Any]:
    """Decode a password-bound reset token. Raises HTTPException."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat", "password_version"]},
        )
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(status_code=400, detail="Reset link has expired") from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(status_code=400, detail="Invalid reset link") from err

    if payload.get("purpose") != "password_reset" or not isinstance(
        payload.get("password_version"), str
    ):
        raise HTTPException(status_code=400, detail="Invalid reset link")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid reset link")
    return payload


def _password_version(password_hash: str | None, secret: str) -> str:
    return hmac.new(
        secret.encode(), (password_hash or "").encode(), hashlib.sha256
    ).hexdigest()


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
        password_hash=user.password_hash,
    )

    # Build reset URL
    origin = config.auth.public_base_url.rstrip("/")
    reset_url = f"{origin}/reset-password?token={token}"

    # Send email
    try:
        from duh.mail import send_email

        send_email(
            config.mail,
            to=user.email,
            subject="Reset your duh password",
            body_html=(
                f"<p>Hi {escape(user.display_name)},</p>"
                f"<p>Click the link below to reset your password. "
                f"This link expires in "
                f"{config.auth.reset_token_expiry_minutes} minutes.</p>"
                f'<p><a href="{escape(reset_url, quote=True)}">'
                f"{escape(reset_url)}</a></p>"
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
    payload = _decode_reset_token(body.token, config.auth.jwt_secret)
    user_id = payload["sub"]

    from sqlalchemy import select, update

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

        if not hmac.compare_digest(
            payload["password_version"],
            _password_version(user.password_hash, config.auth.jwt_secret),
        ):
            raise HTTPException(status_code=400, detail="Invalid reset link")
        previous_hash = user.password_hash
        result = await session.execute(
            update(User)
            .where(
                User.id == user_id,
                User.is_active.is_(True),
                User.password_hash == previous_hash,
            )
            .values(password_hash=hash_password(body.new_password))
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=400, detail="Invalid reset link")
        await session.commit()

    return ResetPasswordResponse(
        message="Password has been reset. You can now sign in."
    )
