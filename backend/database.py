"""
Database engine and session management for Blogger AI Agent.
Uses SQLite for lightweight, zero-dependency local operation.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings

# Create SQLite engine with multi-threading compatibility for FastAPI
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize all database tables and perform lightweight schema upgrades."""
    from backend.models import entities  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite schema migration for added Topic columns
    if "sqlite" in settings.DATABASE_URL:
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info(topics)")).fetchall()
                existing_cols = {row[1] for row in res}
                cols_to_add = [
                    ("source", "VARCHAR(100) DEFAULT 'User'"),
                    ("source_url", "VARCHAR(600) DEFAULT ''"),
                    ("discovery_mode", "VARCHAR(50) DEFAULT 'manual'"),
                    ("trend_evidence", "VARCHAR(200) DEFAULT ''"),
                    ("estimated_difficulty", "VARCHAR(50) DEFAULT 'Intermediate (Estimate)'"),
                    ("audience_fit", "VARCHAR(50) DEFAULT 'High'"),
                    ("article_potential", "VARCHAR(50) DEFAULT 'High'"),
                    ("category", "VARCHAR(100) DEFAULT 'Technology'"),
                ]
                for col_name, col_def in cols_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE topics ADD COLUMN {col_name} {col_def}"))
                conn.commit()
            except Exception as e:
                # Table might not exist yet or other harmless case
                pass
