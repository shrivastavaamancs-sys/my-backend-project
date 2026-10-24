from pydantic import BaseModel, EmailStr, Field


# --- User Schemas ---
class UserCreate(BaseModel):
    # EmailStr ensure karega ki sirf proper email format (jaise user@gmail.com) hi aaye
    email: EmailStr
    
    # Field(..., min_length=...) ensure karega ki password khali ya null na ho
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


# --- Item Schemas ---
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price: float
    is_offer: bool = False


class ItemResponse(ItemCreate):
    id: int
    owner_id: int  # Yeh bhi dikhega ki item kis user ka hai

    class Config:
        from_attributes = True