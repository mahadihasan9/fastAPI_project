import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL, SQLITE_URL, FALLBACK_TO_SQLITE

logger = logging.getLogger("uvicorn.error")

engine = None
SessionLocal = None
Base = declarative_base()

def init_db_engine():
    global engine, SessionLocal
    try:
        if DATABASE_URL.startswith("mysql"):
            # Attempt to connect to MySQL
            test_engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={"connect_timeout": 5}
            )
            # Try a quick test connection
            with test_engine.connect() as conn:
                pass
            engine = test_engine
            logger.info("Successfully connected to MySQL database!")
        else:
            engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
            )
            logger.info("Connected to database: %s", DATABASE_URL)
    except Exception as e:
        if FALLBACK_TO_SQLITE:
            logger.warning(
                "Could not connect to MySQL (%s). Falling back gracefully to SQLite at %s",
                str(e), SQLITE_URL
            )
            engine = create_engine(
                SQLITE_URL,
                connect_args={"check_same_thread": False}
            )
        else:
            raise e

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

# Initialize on import
init_db_engine()

def get_db():
    """Dependency to provide a transactional database session per request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
