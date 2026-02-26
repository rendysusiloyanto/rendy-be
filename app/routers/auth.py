from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.schemas.user import UserResponse, LoginRequest, TokenResponse, SetPasswordRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    email = body.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(body.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token)


@router.put("/me/password")
def set_password(
    body: SetPasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or change password."""
    if len(body.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
    user.password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

# Authlib OAuth - we'll use env from our settings


@router.get("/google/login")
async def google_login():
    """Redirect user to Google consent screen."""
    redirect_uri = settings.google_redirect_uri
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{base_url}?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback, create or get user, return token redirect to frontend."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    import httpx

    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if token_res.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token in response")

    # Get user info from Google
    async with httpx.AsyncClient() as client:
        userinfo_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if userinfo_res.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    userinfo = userinfo_res.json()
    email = userinfo.get("email")
    name = userinfo.get("name") or ""
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    # Get or create user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=name[:100],
            password=None,
            role=UserRole.GUEST.value,
            is_premium=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.full_name and name:
            user.full_name = name[:100]
            db.commit()
            db.refresh(user)

    token = create_access_token(user.id, user.email)
    # Redirect to frontend with token in hash (so it's not sent to server in Referer)
    frontend_callback = f"{settings.frontend_url}/auth/callback?token={token}"
    return RedirectResponse(url=frontend_callback)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        class_name=user.class_name,
        attendance_number=user.attendance_number,
        role=user.role,
        is_premium=user.is_premium,
        is_blacklisted=user.is_blacklisted,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
