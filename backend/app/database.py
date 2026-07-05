import os
import logging
from sqlalchemy import create_engine, text, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.utils import get_data_dir

logger = logging.getLogger(__name__)


DB_DIR = get_data_dir()
os.makedirs(DB_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'agent.db').replace(os.sep, '/')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

@event.listens_for(engine, "connect")
def _set_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign key enforcement on every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migration: add project_path column if it doesn't exist
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN project_path VARCHAR(500)"))
            conn.commit()
    except OperationalError:
        pass  # Column already exists
    except Exception as e:
        logger.warning("Migration project_path failed: %s", e)

    # Migration: add updated_at column to messages if it doesn't exist
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN updated_at TIMESTAMP"))
            conn.commit()
    except OperationalError:
        pass  # Column already exists
    except Exception as e:
        logger.warning("Migration updated_at failed: %s", e)
