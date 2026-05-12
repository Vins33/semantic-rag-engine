"""
I1 — RBAC con JWT Bearer Token.

Ruoli:
  reader  → GET /api/v1/query (solo lettura)
  writer  → POST /api/v1/ingest + tutti i reader
  admin   → tutto, incluso /api/v1/kg/*, /api/v1/tree/*, /api/v1/eval, /api/v1/tuner

Uso (generazione token di sviluppo):
  from app.core.auth import create_access_token
  token = create_access_token({"sub": "alice", "role": "reader"})

Header HTTP:
  Authorization: Bearer <token>
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Configurazione ─────────────────────────────────────────────────────────────
SECRET_KEY: str = os.environ.get(
    "JWT_SECRET_KEY",
    "super-secret-rag-engine-dev-key-change-in-prod-2026",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

VALID_ROLES = {"reader", "writer", "admin"}

# ── Schema ─────────────────────────────────────────────────────────────────────
class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: Optional[int] = None


# ── Creazione token (utility per test/sviluppo) ────────────────────────────────
def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Decodifica e validazione ───────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> TokenPayload:
    try:
        raw = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token non valido: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = raw.get("role", "")
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Ruolo sconosciuto: '{role}'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenPayload(sub=raw.get("sub", ""), role=role, exp=raw.get("exp"))


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TokenPayload:
    """Dipendenza FastAPI: richiede token valido (qualsiasi ruolo)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token mancante. Header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_token(credentials.credentials)


# ── Dipendenze per ruolo ───────────────────────────────────────────────────────
def _require_role(*allowed_roles: str):
    """Factory che ritorna una dipendenza FastAPI per il controllo ruolo."""
    def dependency(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruolo '{user.role}' non autorizzato. Richiesto: {list(allowed_roles)}",
            )
        return user
    return dependency


require_reader = _require_role("reader", "writer", "admin")
require_writer = _require_role("writer", "admin")
require_admin  = _require_role("admin")
