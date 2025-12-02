# app/models/auth_models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: str
    last_name: str
    birthday: str            # YYYY-MM-DD
    gender: Optional[str] = None

class RegisterResponse(BaseModel):
    status: str
    user_id: str
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    status: str
    user_id: str
    token: str

class UpdateGenderRequest(BaseModel):
    gender: str

class UpdateNameRequest(BaseModel):
    display_name: str

class UpdateBirthdayRequest(BaseModel):
    birthday: str   # YYYY-MM-DD