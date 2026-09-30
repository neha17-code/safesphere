from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import User
from ..schemas import LoginIn, PinsIn, RegisterIn, TokenOut, UserOut
from ..security import RateLimiter, create_access_token, hash_secret, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = RateLimiter(limit=10, window_seconds=60)


def _guard(request: Request, email: str):
    ip = request.client.host if request.client else "?"
    if not _limiter.allow(f"{ip}:{email.lower()}"):
        raise HTTPException(429, "Too many attempts. Try again in a minute.")


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, email=u.email, phone=u.phone,
                   has_pins=bool(u.safe_pin_hash and u.duress_pin_hash))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _guard(request, body.email)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(name=body.name.strip(), email=email, phone=body.phone,
                password_hash=hash_secret(body.password))
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _guard(request, body.email)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # same error for unknown email and wrong password -> no account enumeration
    if not user or not verify_secret(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _user_out(user)


@router.put("/pins", status_code=204)
def set_pins(body: PinsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Safe PIN = normal arrival. Duress PIN = looks like arrival but silently raises the alarm."""
    if body.safe_pin == body.duress_pin:
        raise HTTPException(422, "Safe PIN and duress PIN must be different")
    user.safe_pin_hash = hash_secret(body.safe_pin)
    user.duress_pin_hash = hash_secret(body.duress_pin)
    db.commit()
