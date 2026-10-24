from pydantic import BaseModel, EmailStr ,ConfigDict

# User creation aur response schemas...
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str

    # Purana:
    # class Config:
    #     from_attributes = True

    # Naya:
    model_config = ConfigDict(from_attributes=True)

    
# Token schemas (Refresh token ke sath updated)
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    email: str | None = None
    role: str | None = None

# Item schemas
class ItemBase(BaseModel):
    name: str
    price: float
    is_offer: int = 0

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True