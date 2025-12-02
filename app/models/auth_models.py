from pydantic import BaseModel, EmailStr

# ===== Request Models =====
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ===== Response Models =====
class RegisterResponse(BaseModel):
    status: str
    user_id: str
    message: str

class LoginResponse(BaseModel):
    status: str
    user_id: str
    token: str