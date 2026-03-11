import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from workos import AsyncWorkOSClient

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

# WorkOS client
workos_client = AsyncWorkOSClient(
    api_key=settings.WORKOS_API_KEY,
    client_id=settings.WORKOS_CLIENT_ID,
)


def _create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _set_auth_cookie(response: Response, user_id: str) -> None:
    jwt_token = _create_jwt(user_id)
    response.set_cookie(
        key="token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
        max_age=settings.JWT_EXPIRY_DAYS * 24 * 60 * 60,
        path="/",
    )


# ─── Google OAuth (full login with Drive access) ────────────────────────

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


async def _exchange_google_tokens(code: str, redirect_uri: str) -> tuple[dict, dict]:
    """Exchange an authorization code for Google tokens and user info."""
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        token_res.raise_for_status()
        tokens = token_res.json()

        userinfo_res = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {tokens['access_token']}",
        })
        userinfo_res.raise_for_status()
        userinfo = userinfo_res.json()

    return tokens, userinfo


@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    tokens, userinfo = await _exchange_google_tokens(code, settings.GOOGLE_REDIRECT_URI)

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

    response = RedirectResponse(settings.FRONTEND_URL, status_code=302)
    _set_auth_cookie(response, user.id)
    return response


# ─── WorkOS SSO ──────────────────────────────────────────────────────────

@router.get("/workos/login")
async def workos_login():
    authorization_url = workos_client.sso.get_authorization_url(
        organization_id=settings.WORKOS_ORGANIZATION_ID,
        redirect_uri=settings.WORKOS_REDIRECT_URI,
    )
    return RedirectResponse(authorization_url)


@router.get("/workos/callback")
async def workos_callback(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if error or not code:
        logger.error("WorkOS SSO error: %s - %s", error, error_description)
        msg = error_description or error or "SSO login failed"
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/login?error={msg}",
            status_code=302,
        )
    profile_and_token = await workos_client.sso.get_profile_and_token(code)
    profile = profile_and_token.profile

    # Check if this WorkOS user already exists
    result = await db.execute(
        select(User).where(User.workos_user_id == profile.id)
    )
    user = result.scalar_one_or_none()

    if user:
        user.email = profile.email
        user.name = profile.first_name or profile.email
    else:
        # Check if a user with this email already exists (e.g. previously signed in with Google)
        result = await db.execute(
            select(User).where(User.email == profile.email)
        )
        user = result.scalar_one_or_none()

        if user:
            # Link the WorkOS identity to the existing account
            user.workos_user_id = profile.id
            user.name = profile.first_name or user.name
        else:
            user = User(
                email=profile.email,
                name=profile.first_name or profile.email,
                workos_user_id=profile.id,
            )
            db.add(user)

    await db.commit()
    await db.refresh(user)

    response = RedirectResponse(settings.FRONTEND_URL, status_code=302)
    _set_auth_cookie(response, user.id)
    return response


# ─── Google Drive connect (for SSO users without Drive access) ───────────

GOOGLE_DRIVE_REDIRECT_URI = settings.GOOGLE_REDIRECT_URI.replace(
    "/google/callback", "/google/connect/callback"
)

@router.get("/google/connect")
async def google_connect(user: User = Depends(get_current_user)):
    """Initiate Google OAuth to connect Drive access for an already-authenticated user."""
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_DRIVE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/connect/callback")
async def google_connect_callback(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle the Google OAuth callback to link Drive access to an existing user."""
    tokens, userinfo = await _exchange_google_tokens(code, GOOGLE_DRIVE_REDIRECT_URI)

    expires_at = None
    if "expires_in" in tokens:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    user.google_id = userinfo["id"]
    user.google_access_token = tokens["access_token"]
    if tokens.get("refresh_token"):
        user.google_refresh_token = tokens["refresh_token"]
    user.token_expires_at = expires_at

    await db.commit()

    return RedirectResponse(settings.FRONTEND_URL, status_code=302)


# ─── Session ─────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture_url,
        "google_drive_connected": user.google_access_token is not None,
    }


@router.post("/logout")
async def logout():
    response = Response(status_code=204)
    response.delete_cookie("token", path="/")
    return response
