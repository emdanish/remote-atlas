from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    headline: Optional[str] = Field(default=None, max_length=512)
    bio: Optional[str] = Field(default=None, max_length=5000)
    experience_level: Optional[Literal["internship", "junior", "mid", "senior"]] = None
    # Resume parse often yields 40–100 tags; keep headroom without unbounded payloads
    skills: Optional[list[str]] = Field(default=None, max_length=120)
    technologies: Optional[list[str]] = Field(default=None, max_length=120)
    desired_roles: Optional[list[str]] = Field(default=None, max_length=30)
    location_preference: Optional[str] = Field(default=None, max_length=255)
    remote_preference: Optional[Literal["remote", "hybrid", "onsite", "any"]] = None
    cities: Optional[list[str]] = Field(default=None, max_length=30)
    pakistan_friendly: Optional[bool] = None

    @field_validator("skills", "technologies", "desired_roles", "cities")
    @classmethod
    def normalize_list_fields(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value:
                continue
            if len(value) > 100:
                raise ValueError("List entries must be 100 characters or fewer")
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(value)
        return cleaned

    @field_validator("headline", "bio", "location_preference")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    headline: Optional[str] = None
    bio: Optional[str] = None
    experience_level: str = "junior"
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    desired_roles: list[str] = Field(default_factory=list)
    location_preference: Optional[str] = None
    remote_preference: str = "remote"
    cities: list[str] = Field(default_factory=list)
    pakistan_friendly: bool = True


class OnboardingOut(BaseModel):
    has_profile: bool = False
    has_skills: bool = False
    has_resume: bool = False
    has_desired_roles: bool = False
    onboarding_complete: bool = False
    seed_skills: list[str] = Field(default_factory=list)
    completion_percent: int = 0
    resume_uploaded_at: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    profile: Optional[ProfileOut] = None
    onboarding: Optional[OnboardingOut] = None


class SavedJobCreate(BaseModel):
    job_id: int
    notes: Optional[str] = Field(default=None, max_length=5000)
    status: Literal["saved", "applied", "interview", "offer", "rejected"] = "saved"


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    notes: Optional[str] = None
    status: str
    created_at: datetime
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    apply_url: Optional[str] = None
