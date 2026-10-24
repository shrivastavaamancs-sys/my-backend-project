from datetime import datetime, timedelta
import os

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, status

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

# Local imports
import models
from database import engine, get_db
from models import ItemModel, UserModel
import schemas

# --- 1. CONFIGURATIONS & INITIALIZATIONS ---

# .env file ki values load karne ke liye
load_dotenv()

# Limiter initialize karna (client ke IP address ke basis par)
limiter = Limiter(key_func=get_remote_address)

# FastAPI app initialize karna (Sirf ek baar)
app = FastAPI(title="Production Ready FastAPI App", version="1.0.0")

# App par limiter state aur exception handler set karna
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Environment Variables
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_if_env_is_missing")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- 2. CORS MIDDLEWARE ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 3. CUSTOM EXCEPTION HANDLER ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "status_code": exc.status_code,
            "message": exc.detail,
        },
    )


# --- 4. HELPER FUNCTIONS & AUTHENTICATION ---

def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin_user(current_user: UserModel = Depends(get_current_user)):
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Admin only)",
        )
    return current_user


# Database tables create karna
models.Base.metadata.create_all(bind=engine)


# --- 5. ROUTES ---

# A. Root Route (Serves index.html as requested)
@app.get("/")
def read_index():
    return FileResponse("index.html")

# Dashboard HTML file serve karne ke liye route
@app.get("/dashboard.html")
def read_dashboard():
    return FileResponse("dashboard.html")

# B. API Health / Status Check Route
@app.get("/api/health")
def health_check():
    return {"message": "Production-ready FastAPI backend with Auth is running!"}


# --- 6. USER AUTHENTICATION & REGISTRATION APIS ---

# Register API
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = UserModel(email=user.email, hashed_password=hashed_password)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# Login API (Rate limited: 5 requests per minute)
@app.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# Get All Users
@app.get("/users/", response_model=list[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(UserModel).all()


# --- 7. ITEM APIS (CRUD & User Linked) ---

# Create Item (Protected Route)
@app.post("/items/", response_model=schemas.ItemResponse)
def create_item(
    item: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_item = ItemModel(
        name=item.name,
        price=item.price,
        is_offer=int(item.is_offer),
        owner_id=current_user.id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


# Get All Items
@app.get("/items/", response_model=list[schemas.ItemResponse])
def get_items(db: Session = Depends(get_db)):
    return db.query(ItemModel).all()


# Get Single Item by ID
@app.get("/items/{item_id}", response_model=schemas.ItemResponse)
def get_single_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# Update Item
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


# Delete Item
@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found to delete")

    db.delete(item)
    db.commit()
    return {"message": f"Item with ID {item_id} deleted successfully!"}


# --- 8. ADMIN ROUTES ---
# --- 8. ADMIN ROUTES ---

# Admin Dashboard (Protected & Role Restricted)
@app.get("/admin/dashboard")
def admin_dashboard(admin_user: UserModel = Depends(get_current_admin_user)):
    return {
        "message": f"Welcome to Admin Dashboard, {admin_user.email}!"
    }

# Yahan /token aur /login dono laga dein taaki 404 Not Found error na aaye
@app.post("/token")
@app.post("/login")
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}