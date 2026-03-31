from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import LoginRequest, RegisterRequest
from src.api.security import (
    create_auth_response,
    get_current_user,
    hash_password,
    normalize_identifier,
    serialize_user,
    verify_password,
)
from src.db.database import get_db
from src.db.models import User
from src.db.repositories import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    username = payload.username.strip()
    email = normalize_identifier(payload.email)

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    repo = UserRepository(db)
    existing = await repo.get_by_username_or_email(username, email)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with that username or email already exists",
        )

    user = await repo.create(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password),
    )
    return create_auth_response(user)


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = payload.identifier.strip()
    normalized = normalize_identifier(identifier)

    repo = UserRepository(db)
    user = await repo.get_by_identifier(identifier, normalized)

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return create_auth_response(user)


@router.get("/me")
async def auth_me(current_user: User = Depends(get_current_user)):
    return {"user": serialize_user(current_user)}
