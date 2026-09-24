import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# File paths
ADMIN_KEY_FILE = BASE_DIR / "adminkey.txt"
API_KEY_FILE = BASE_DIR / "apikey.txt"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://fastapi_user:secretpassword@localhost:3306/photo_db")
FALLBACK_TO_SQLITE = os.getenv("FALLBACK_TO_SQLITE", "True").lower() in ("true", "1", "t")
SQLITE_URL = f"sqlite:///{BASE_DIR / 'app.db'}"

# Security Configurations
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", 5))
BLOCK_DURATION_MINUTES = int(os.getenv("BLOCK_DURATION_MINUTES", 60))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
ADMIN_RATE_LIMIT_PER_MINUTE = int(os.getenv("ADMIN_RATE_LIMIT_PER_MINUTE", 10))
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "fastapi_super_secret_session_key_2026")

def get_admin_password() -> str:
    """
    Returns the administrator password.

    Priority:
      1. ADMIN_PASSWORD environment variable (recommended for Docker/VPS deploys
         so the secret is never baked into the image)
      2. adminkey.txt on disk (local development / mounted file)
      3. Generated default (admin@secret123) when neither exists
    """
    env_value = os.getenv("ADMIN_PASSWORD", "").strip()
    if env_value:
        return env_value

    if not ADMIN_KEY_FILE.exists():
        ADMIN_KEY_FILE.write_text("admin@secret123", encoding="utf-8")
        return "admin@secret123"
    content = ADMIN_KEY_FILE.read_text(encoding="utf-8").strip()
    if not content:
        ADMIN_KEY_FILE.write_text("admin@secret123", encoding="utf-8")
        return "admin@secret123"
    return content

def get_api_key() -> str:
    """
    Returns the public API key.

    Priority:
      1. API_KEY environment variable (recommended for Docker/VPS deploys)
      2. apikey.txt on disk (local development / mounted file)
      3. Generated default (my_secure_api_key_2026) when neither exists
    """
    env_value = os.getenv("API_KEY", "").strip()
    if env_value:
        return env_value

    if not API_KEY_FILE.exists():
        API_KEY_FILE.write_text("my_secure_api_key_2026", encoding="utf-8")
        return "my_secure_api_key_2026"
    content = API_KEY_FILE.read_text(encoding="utf-8").strip()
    if not content:
        API_KEY_FILE.write_text("my_secure_api_key_2026", encoding="utf-8")
        return "my_secure_api_key_2026"
    return content
