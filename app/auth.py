from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

settings = get_settings()
security = HTTPBearer(auto_error=False)

# Use Argon2 for password hashing
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_token(token: str) -> TokenPayload | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            email=payload["email"],
            exp=payload["exp"],
        )
    except JWTError:
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == payload.sub).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# Uniform message for blacklisted users (used by endpoints that block access)
BLACKLIST_MESSAGE = "Account is blocked. Please contact admin to request access."


def get_current_user_premium(
    user: User = Depends(get_current_user),
) -> User:
    """User must be logged in and is_premium=True."""
    if not user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is for premium accounts only.",
        )
    return user


def get_current_user_premium_not_blacklisted(
    user: User = Depends(get_current_user_premium),
) -> User:
    """User must be premium and not blacklisted. For OpenVPN create/status/download."""
    if user.is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=BLACKLIST_MESSAGE,
        )
    return user


def require_not_blacklisted(user: User = Depends(get_current_user)) -> User:
    """User must be logged in and not blacklisted. For VPN, test, open learning detail."""
    if user.is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=BLACKLIST_MESSAGE,
        )
    return user


def get_user_from_token(token: str, db: Session) -> User | None:
    """For WebSocket: get user from token string. Returns None if invalid."""
    payload = decode_token(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload.sub).first()


def get_current_user_admin(
    user: User = Depends(get_current_user),
) -> User:
    """User must be logged in and have ADMIN role."""
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can access.",
        )
    return user