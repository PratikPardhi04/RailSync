from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _run_migrations():
    with engine.connect() as conn:
        if "sqlite" in DATABASE_URL:
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(maintenance_requests)"))]
            if cols and "request_metadata" not in cols:
                conn.execute(text("ALTER TABLE maintenance_requests ADD COLUMN request_metadata TEXT"))

def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()
