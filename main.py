from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import models
from models import ItemModel, User, UserModel
from passlib.context import CryptContext
import schemas
from slowapi import _rate_limit_exceeded_handler, Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from database import engine, get_db
from fastapi import Depends, FastAPI, HTTPException, Request, status

# .env file ki values load karne ke liye
load_dotenv()

# Limiter initialize karna (client ke IP address ke basis par)
limiter = Limiter(key_func=get_remote_address)

# FastAPI app initialize karna (app banne ke baad hi state set hoti hai)
app = FastAPI()

# App par limiter state aur exception handler set karna
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# SECRET_KEY ab safe tarike se .env file se uthegi!
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_if_env_is_missing")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# Helper functions
def get_password_hash(password):
  return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
  return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
  to_encode = data.copy()
  expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  to_encode.update({"exp": expire})
  return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- GET CURRENT LOGGED-IN USER ---
def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
  credentials_exception = HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Could not validate credentials",
      headers={"WWW-Authenticate": "Bearer"},
  )
  try:
    # Token ko decode karke email nikalna
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    email: str = payload.get("sub")
    if email is None:
      raise credentials_exception
  except JWTError:
    raise credentials_exception

  # Database mein check karna ki user sach mein exist karta hai ya nahi
  user = db.query(UserModel).filter(UserModel.email == email).first()
  if user is None:
    raise credentials_exception
  return user


# Database tables create karna
models.Base.metadata.create_all(bind=engine)

app = FastAPI()


# Custom Global Exception Handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc: HTTPException):
  return JSONResponse(
      status_code=exc.status_code,
      content={
          "success": False,
          "status_code": exc.status_code,
          "message": exc.detail,
      },
  )


# --- CORS MIDDLEWARE CONFIGURATION ---
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
  return {"message": "Production-ready FastAPI backend with Auth is running!"}


# --- 1. USER AUTHENTICATION & REGISTRATION APIS ---


# A. Register API (Password hash hokar save hoga)
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
  db_user = db.query(UserModel).filter(UserModel.email == user.email).first()
  if db_user:
    raise HTTPException(status_code=400, detail="Email already registered")

  hashed_password = get_password_hash(user.password)

  # Yahan 'password' ki jagah 'hashed_password' karein:
  new_user = UserModel(email=user.email, hashed_password=hashed_password)

  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return new_user


# B. Login API (JWT Token generate karne ke liye)
@app.post("/login")
@limiter.limit("5/minute")  # <--- Yahan limit laga di hai
def login(
    request: Request,  # Note: slowapi ke liye yahan 'request: Request' add karna zaroori hai
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
  user = (
      db.query(UserModel).filter(UserModel.email == form_data.username).first()
  )
  if not user or not verify_password(
      form_data.password, user.hashed_password
  ):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

  access_token = create_access_token(data={"sub": user.email})
  return {"access_token": access_token, "token_type": "bearer"}

# C. Get All Users
@app.get("/users/", response_model=list[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
  return db.query(UserModel).all()


# --- 2. ITEM APIS (Linked with Users & CRUD) ---


# A. Create Item for Logged-in User (Protected Route)
@app.post("/items/", response_model=schemas.ItemResponse)
def create_item(
    item: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(
        get_current_user
    ),  # Yahan token se user automatic detect hoga
):
  db_item = ItemModel(
      name=item.name,
      price=item.price,
      is_offer=int(item.is_offer),
      owner_id=current_user.id,  # Logged-in user ki ID sidhe yahan assign ho jayegi
  )
  db.add(db_item)
  db.commit()
  db.refresh(db_item)
  return db_item


# B. Get All Items
@app.get("/items/", response_model=list[schemas.ItemResponse])
def get_items(db: Session = Depends(get_db)):
  return db.query(ItemModel).all()


# C. Get Item by ID
@app.get("/items/{item_id}", response_model=schemas.ItemResponse)
def get_single_item(item_id: int, db: Session = Depends(get_db)):
  item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
  if item is None:
    raise HTTPException(status_code=404, detail="Item not found")
  return item


# D. Update Item
@app.put("/items/{item_id}")
def update_item(
    item_id: int, updated_item: schemas.ItemCreate, db: Session = Depends(get_db)
):
  item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
  if item is None:
    raise HTTPException(status_code=404, detail="Item not found to update")

  item.name = updated_item.name
  item.price = updated_item.price
  item.is_offer = int(updated_item.is_offer)

  db.commit()
  db.refresh(item)
  return {"message": "Item updated successfully!", "item": item}


# E. Delete Item
@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
  item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
  if item is None:
    raise HTTPException(status_code=404, detail="Item not found to delete")

  db.delete(item)
  db.commit()
  return {"message": f"Item with ID {item_id} deleted successfully!"}
from fastapi import Depends, HTTPException, status


# Yeh dependency sirf admin users ko allow karegi
def get_current_admin_user(current_user: User = Depends(get_current_user)):
  if current_user.role != "admin":
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The user doesn't have enough privileges (Admin only)",
    )
  return current_user


# Yeh ek test admin route hai
@app.get("/admin/dashboard")
def admin_dashboard(admin_user: User = Depends(get_current_admin_user)):
  return {
      "message": f"Welcome to Admin Dashboard, {admin_user.email}!"
  }

# Yeh dependency sirf admin users ko allow karegi
def get_current_admin_user(current_user: User = Depends(get_current_user)):
  if current_user.role != "admin":
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The user doesn't have enough privileges (Admin only)",
    )
  return current_user

