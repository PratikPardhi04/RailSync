from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.security import decode_token
from app.models.models import User


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_engineer(user: User = Depends(get_current_user)) -> User:
    if user.role != "engineer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer access required")
    return user


def require_officer(user: User = Depends(get_current_user)) -> User:
    if user.role != "officer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Officer access required")
    return user
