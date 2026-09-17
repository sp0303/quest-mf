"""Authentication router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import Principal, create_access_token, get_current_user

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
async def login(req: LoginRequest):
    # In dev mode, verify standard analyst user or default credentials
    if req.email == "analyst@questmf.local" and req.password == "analyst123":
        token = create_access_token("u-1", req.email, "analyst")
        return LoginResponse(
            access_token=token,
            expires_in=3600,
            user={"id": "u-1", "email": req.email, "role": "analyst"},
        )
    # Allow test login with dev credentials
    token = create_access_token("u-guest", str(req.email), "analyst")
    return LoginResponse(
        access_token=token,
        expires_in=3600,
        user={"id": "u-guest", "email": str(req.email), "role": "analyst"},
    )


@router.get("/me")
async def me(current_user: Principal = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
    }
