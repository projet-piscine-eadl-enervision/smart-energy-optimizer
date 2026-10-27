"""Routes d'authentification : inscription, connexion, profil courant."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, LoginThrottleDep
from app.core.login_throttle import mask_email, normalize_email
from app.core.metrics import LOGIN_ATTEMPTS
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Email ou mot de passe incorrect"
TOO_MANY_ATTEMPTS = "Trop de tentatives de connexion, réessayez plus tard"


@router.post("/register", response_model=UserRead, summary="Account creation", status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DbSession):
    email = normalize_email(payload.email)
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email déjà utilisé")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login page",
    responses={429: {"description": "Trop de tentatives : réessayer après Retry-After secondes"}},
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: DbSession,
    throttle: LoginThrottleDep,
):
    # OAuth2PasswordRequestForm fournit .username (= email ici) et .password
    email = normalize_email(form.username)
    ip = request.client.host if request.client else "unknown"

    # Avant toute lecture du compte et tout calcul bcrypt : un blocage coûte peu au serveur
    block = await throttle.check(ip, email)
    if block:
        LOGIN_ATTEMPTS.labels(f"{block.reason}_blocked").inc()
        logger.warning(
            "login blocked reason=%s ip=%s email=%s retry_after=%s",
            block.reason, ip, mask_email(email), block.retry_after,
        )
        # Même réponse pour un blocage par IP ou par e-mail, que le compte existe ou non
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            TOO_MANY_ATTEMPTS,
            headers={"Retry-After": str(block.retry_after)},
        )

    user = await db.scalar(select(User).where(User.email == email))
    # Toujours un calcul bcrypt, compte connu ou non
    hashed = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(form.password, hashed)
    if not password_ok or not user or not user.is_active:
        # Un compte désactivé reçoit le même 401 : la réponse ne révèle pas son état
        outcome = "inactive_account" if password_ok and user else "invalid_credentials"
        await throttle.record_failure(ip, email)
        LOGIN_ATTEMPTS.labels(outcome).inc()
        logger.warning(
            "login failed reason=%s ip=%s email=%s user_id=%s",
            outcome, ip, mask_email(email), user.id if user else None,
        )
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    await throttle.record_success(email)
    LOGIN_ATTEMPTS.labels("success").inc()
    logger.info("login succeeded ip=%s user_id=%s", ip, user.id)
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserRead, summary="User profile")
async def me(current_user: CurrentUser):
    """Route protégée : renvoie le profil du porteur du jeton."""
    return current_user
