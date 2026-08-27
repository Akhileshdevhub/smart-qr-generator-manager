from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    # Minimum length is a cheap first line of defence; real strength rules are
    # documented as a future improvement.
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    # from_attributes lets FastAPI build this straight from a SQLAlchemy row.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    display_name: str = Field(max_length=120)
