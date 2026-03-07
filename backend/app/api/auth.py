import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


@router.get("/google/login")
async def google_login():
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        token_res.raise_for_status()
        tokens = token_res.json()

        # Get user info
        userinfo_res = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {tokens['access_token']}",
        })
        userinfo_res.raise_for_status()
        userinfo = userinfo_res.json()

    # Find or create user
    result = await db.execute(
        select(User).where(User.google_id == userinfo["id"])
    )
    user = result.scalar_one_or_none()

    expires_at = None
    if "expires_in" in tokens:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    if user:
        user.email = userinfo["email"]
        user.name = userinfo.get("name", userinfo["email"])
        user.picture_url = userinfo.get("picture")
        user.google_access_token = tokens["access_token"]
        if tokens.get("refresh_token"):
            user.google_refresh_token = tokens["refresh_token"]
        user.token_expires_at = expires_at
    else:
        user = User(
            email=userinfo["email"],
            name=userinfo.get("name", userinfo["email"]),
            picture_url=userinfo.get("picture"),
            google_id=userinfo["id"],
            google_access_token=tokens["access_token"],
            google_refresh_token=tokens.get("refresh_token"),
            token_expires_at=expires_at,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Set JWT cookie and redirect to frontend
    jwt_token = _create_jwt(user.id)
    response = RedirectResponse(settings.FRONTEND_URL, status_code=302)
    response.set_cookie(
        key="token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
        max_age=settings.JWT_EXPIRY_DAYS * 24 * 60 * 60,
        path="/",
    )
    return response


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture_url,
    }


@router.post("/logout")
async def logout():
    response = Response(status_code=204)
    response.delete_cookie("token", path="/")
    return response
