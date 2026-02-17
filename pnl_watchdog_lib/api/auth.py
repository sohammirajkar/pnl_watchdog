"""
Authentication helpers for API key onboarding and tenant isolation.
"""

import hashlib
import secrets
from typing import Optional, Tuple

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.db_connect import get_db
from ..db.models import User


class RegisterRequest(BaseModel):
    """Request body for creating a user API key."""
    email: str = Field(..., min_length=5, max_length=255)


class RegisterResponse(BaseModel):
    """Response returned when user API key is created or rotated."""
    user_id: str
    email: str
    api_key: str


def hash_api_key(raw_api_key: str) -> str:
    """Store only a deterministic hash of API keys at rest."""
    return hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate a human-readable API key."""
    return f"pnlw_{secrets.token_urlsafe(24)}"


async def create_or_rotate_api_key(db: AsyncSession, email: str) -> Tuple[User, str]:
    """
    Create a user if missing, or rotate key if user already exists.
    Returns the user row and plaintext key (shown once).
    """
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required.")

    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()

    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)

    if user:
        user.api_key = key_hash
    else:
        user = User(email=normalized_email, api_key=key_hash)
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user, plain_key


async def get_current_user(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve user from API key header.
    Accepts hashed lookup and plain lookup for backward compatibility.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")

    hashed_key = hash_api_key(x_api_key)
    result = await db.execute(select(User).where(User.api_key == hashed_key))
    user = result.scalar_one_or_none()

    if user is None:
        # Backward compatibility for older rows that stored plain keys.
        fallback = await db.execute(select(User).where(User.api_key == x_api_key))
        user = fallback.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return user
