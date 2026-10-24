from database import Base
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)  # Khali nahi chhoot sakta
    hashed_password = Column(String, nullable=False)                 # Required hai
    role = Column(String, default="user", nullable=False)

    items = relationship("Item", back_populates="owner", cascade="all, delete")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    is_offer = Column(Integer, default=0)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="items")


# Backup Aliases (Taaki main.py mein chahe User/Item likho ya UserModel/ItemModel, error na aaye)
UserModel = User
ItemModel = Item