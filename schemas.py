from pydantic import BaseModel


# --- User Schemas ---
class UserCreate(BaseModel):
  email: str
  password: str


class UserResponse(BaseModel):
  id: int
  email: str

  class Config:
    from_attributes = True


# --- Item Schemas ---
class ItemCreate(BaseModel):
  name: str
  price: float
  is_offer: bool = False


class ItemResponse(ItemCreate):
  id: int
  owner_id: int  # Yeh bhi dikhega ki item kis user ka hai

  class Config:
    from_attributes = True