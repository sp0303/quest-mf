"""Authentication router with real DB lookup, Argon2id, RS256, and JWKS."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.db import get_db_connection
from app.core.security import (
    Principal,
    create_access_token,
    get_current_user,
    get_jwks,
    verify_password,
)

router = APIRouter(prefix="/auth/v1", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Authenticate with email and password against auth.users using Argon2id."""
    row = await conn.fetchrow(
        """
        SELECT user_id, email, password_hash, role, is_active
        FROM auth.users
        WHERE email = $1;
    """,
        req.email.strip().lower(),
    )

    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(req.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(row["user_id"]), row["email"], row["role"])
    return LoginResponse(
        access_token=token,
        expires_in=3600,
        user={"id": str(row["user_id"]), "email": row["email"], "role": row["role"]},
    )


@router.get("/me")
async def me(current_user: Principal = Depends(get_current_user)):
    """Return currently authenticated principal."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get("/.well-known/jwks.json")
async def jwks():
    """Expose public keys for stateless RS256 verification."""
    return get_jwks()
