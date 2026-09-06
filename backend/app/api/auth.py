from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.models import User
from app.schemas.schemas import LoginRequest, TokenResponse
from app.auth.security import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": str(user.id), "role": user.role, "name": user.name, "email": user.email})

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    )


@router.get("/me")
def get_me(token: str = None, db: Session = Depends(get_db)):
    from fastapi import Request
    return {"message": "Use Authorization header"}
