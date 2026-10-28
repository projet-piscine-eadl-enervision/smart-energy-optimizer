"""Dépendances FastAPI partagées — surtout : récupérer l'utilisateur courant.

get_current_user() lit le jeton Bearer, le vérifie, et charge l'utilisateur.
On la pose sur toute route à protéger : sans jeton valide → 401 automatique.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.login_throttle import LoginThrottle, SqlFailureStore
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import Role, User

# tokenUrl = l'endpoint où le front récupère son jeton
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_login_throttle(db: DbSession) -> LoginThrottle:
    """Compteurs d'échecs de /auth/login, en base (partagés entre instances de l'API)."""
    return LoginThrottle(SqlFailureStore(db))


LoginThrottleDep = Annotated[LoginThrottle, Depends(get_login_throttle)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Jeton invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = await db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_error

    return user


# Raccourci réutilisable : CurrentUser dans la signature d'une route la protège
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role):
    """Fabrique une dépendance qui exige l'un des rôles donnés.

    Jeton absent/invalide → 401 (via CurrentUser) ; rôle insuffisant → 403.
    """

    async def checker(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé")
        return current_user

    return checker


# Raccourci : AdminUser dans la signature d'une route la réserve aux admins
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


def site_scope(user: User, site_id: str | None) -> str | None:
    """Site que l'utilisateur a le droit de lire, à passer aux requêtes à la place de site_id.

    - admin : le site demandé, ou None pour tous les sites ;
    - user : toujours son propre site, même sans site_id (le « total » devient son site) ;
      un autre site → 403, aucun site attribué → 403.
    """
    if user.role == Role.ADMIN:
        return site_id
    if user.site_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Aucun site attribué à ce compte")
    if site_id is not None and site_id != user.site_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé à ce site")
    return user.site_id
