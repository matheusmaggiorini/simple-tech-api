"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from api.core.database import create_user, get_user_by_email
from api.core.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    try:
        user = create_user(
            email=body.email,
            name=body.name,
            hashed_password=hash_password(body.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_access_token(user["id"], user["email"])
    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if user is None or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user["id"], user["email"])
    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )
