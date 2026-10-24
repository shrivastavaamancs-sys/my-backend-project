from datetime import datetime, timedelta,timezone
import os
from dotenv import load_dotenv

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, status, Request, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
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

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Production Ready FastAPI App with Refresh Token", version="1.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Environment Variables
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_if_env_is_missing")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        # Purana: expire = datetime.utcnow() + expires_delta
         expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
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


from fastapi import Security

# 1. Yeh function wahan rakhein jahan aapki security dependencies hain (get_current_user ke niche)
def require_roles(allowed_roles: list[str]):
    def role_verifier(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return current_user
    return role_verifier


# 2. Yeh naye protected routes aap apni file ke baaki routes ke sath kahin bhi jodh sakte hain:

# Sirf Admin ke liye
@app.get("/admin/analytics", dependencies=[Depends(require_roles(["admin"]))])
def get_admin_analytics():
    return {"message": "Welcome Admin! Here is the analytics data."}

# Admin aur Manager dono ke liye
@app.get("/management/reports", dependencies=[Depends(require_roles(["admin", "manager"]))])
def get_management_reports():
    return {"message": "Welcome Admin or Manager! Here are the business reports."}

def get_current_admin_user(current_user: UserModel = Depends(get_current_user)):
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Admin only)",
        )
    return current_user

# Create database tables
models.Base.metadata.create_all(bind=engine)

# --- 5. ROUTES ---

@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/dashboard.html")
def read_dashboard():
    return FileResponse("dashboard.html")

@app.get("/api/health")
def health_check():
    return {"message": "Production-ready FastAPI backend with Auth & Refresh Token is running!"}

# A. Logged-in user ki details fetch karne ke liye endpoint
@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# B. Profile page serve karne ke liye route
@app.get("/profile.html")
def read_profile():
    return FileResponse("profile.html")

@app.get("/profile.html")
def read_profile():
    return FileResponse("profile.html")

# --- 6. USER AUTHENTICATION & REGISTRATION APIS ---

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

# Login & Token Endpoint (Returns Access & Refresh Tokens)
@app.post("/token", response_model=schemas.Token)
@app.post("/login", response_model=schemas.Token)
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

    # Generate Access and Refresh Tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": getattr(user, "role", "user")}, 
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.email})

    # Save refresh token in DB
    user.refresh_token = refresh_token
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Refresh Token Endpoint
@app.post("/refresh", response_model=schemas.Token)
def refresh_access_token(request_body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(request_body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user or getattr(user, "refresh_token", None) != request_body.refresh_token:
        raise credentials_exception

    # Generate new Access Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": getattr(user, "role", "user")}, 
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": request_body.refresh_token,
        "token_type": "bearer"
    }

@app.get("/users/", response_model=list[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(UserModel).all()

# --- 7. ITEM APIS (CRUD & User Linked) ---

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

@app.get("/items/", response_model=list[schemas.ItemResponse])
def get_items(db: Session = Depends(get_db)):
    return db.query(ItemModel).all()

@app.get("/items/{item_id}", response_model=schemas.ItemResponse)
def get_single_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

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

@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found to delete")

    db.delete(item)
    db.commit()
    return {"message": f"Item with ID {item_id} deleted successfully!"}

# --- 8. ADMIN ROUTES ---

@app.get("/admin/dashboard")
def admin_dashboard(admin_user: UserModel = Depends(get_current_admin_user)):
    return {
        "message": f"Welcome to Admin Dashboard, {admin_user.email}!"
    }