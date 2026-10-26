"""Routes d'authentification : inscription, connexion, profil courant."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DbSession):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email déjà utilisé")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    # OAuth2PasswordRequestForm fournit .username (= email ici) et .password
    user = await db.scalar(select(User).where(User.email == form.username))
    # Toujours un calcul bcrypt, compte connu ou non
    hashed = user.hashed_password if user else DUMMY_HASH
    if not verify_password(form.password, hashed) or not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser):
    """Route protégée : renvoie le profil du porteur du jeton."""
    return current_user
