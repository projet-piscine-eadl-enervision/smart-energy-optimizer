"""Modèle utilisateur — table SQL pour l'authentification."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(str, enum.Enum):
    """Rôles possibles. Hérite de str : sérialisé tel quel en JSON ("user")."""

    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda e: [r.value for r in e]),
        default=Role.USER,
        server_default=Role.USER.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Site de rattachement (ref.site, contrainte posée par la migration) : un `user` ne lit que celui-ci,
    # un `admin` lit tous les sites. Vide = aucun site attribué
    site_id: Mapped[str | None] = mapped_column(String, default=None)
