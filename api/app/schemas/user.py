"""Schémas Pydantic : ce qui entre et sort de l'API pour les utilisateurs.

Séparer les schémas des modèles SQL évite d'exposer le hash du mot de passe :
UserRead ne contient jamais hashed_password.
UserCreate ne contient jamais role : impossible de s'inscrire en admin.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.user import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # En octets et non en caractères : un « é » en occupe deux
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"au plus {MAX_PASSWORD_BYTES} octets")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    role: Role
    created_at: datetime
