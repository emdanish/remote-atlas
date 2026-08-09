from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.db.session import get_db
from app.models import Profile, User
from app.matching.scoring import profile_onboarding_state
from app.schemas.auth import (
    LoginRequest,
    OnboardingOut,
    ProfileOut,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.security import enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await enforce_rate_limit(request, "register", limit=5, period_seconds=300, identity=body.email)
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()
    db.add(
        Profile(
            user_id=user.id,
            experience_level="junior",
            remote_preference="remote",
            pakistan_friendly=True,
            skills=[],
            technologies=[],
            desired_roles=[],
            cities=[],
        )
    )
    await db.commit()
    token = create_access_token(user.id, extra={"email": user.email})
    _set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await enforce_rate_limit(request, "login", limit=10, period_seconds=300, identity=body.email)
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, extra={"email": user.email})
    _set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    profile = None
    onboarding = OnboardingOut(**profile_onboarding_state(user.profile))
    if user.profile:
        profile = ProfileOut(
            headline=user.profile.headline,
            bio=user.profile.bio,
            experience_level=user.profile.experience_level,
            skills=user.profile.skills or [],
            technologies=user.profile.technologies or [],
            desired_roles=user.profile.desired_roles or [],
            location_preference=user.profile.location_preference,
            remote_preference=user.profile.remote_preference,
            cities=user.profile.cities or [],
            pakistan_friendly=user.profile.pakistan_friendly,
        )
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        profile=profile,
        onboarding=onboarding,
    )


@router.put("/me/profile", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    user = result.scalar_one()
    if not user.profile:
        user.profile = Profile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user.profile, key, value)
    await db.commit()
    await db.refresh(user.profile)
    p = user.profile
    return ProfileOut(
        headline=p.headline,
        bio=p.bio,
        experience_level=p.experience_level,
        skills=p.skills or [],
        technologies=p.technologies or [],
        desired_roles=p.desired_roles or [],
        location_preference=p.location_preference,
        remote_preference=p.remote_preference,
        cities=p.cities or [],
        pakistan_friendly=p.pakistan_friendly,
    )
