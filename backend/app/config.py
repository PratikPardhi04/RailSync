import os

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./raillink.db")
SECRET_KEY = os.getenv("SECRET_KEY", "raillink-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

if not GROQ_API_KEY:
    DEMO_MODE = True
