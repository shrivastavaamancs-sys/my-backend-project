from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Password ke '@' ko '%40' se replace kar diya hai
SQLALCHEMY_DATABASE_URL = (
    "postgresql+psycopg2://postgres:Anshul%40789@localhost:5432/my_backend_db"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency function
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()