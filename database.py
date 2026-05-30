from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime

engine = create_engine("sqlite:///painpoints.db", echo=False)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class PainPoint(Base):
    __tablename__ = "painpoints"

    id = Column(String, primary_key=True)
    source = Column(String)           # subreddit
    author = Column(String)
    title = Column(String)
    body = Column(Text)
    url = Column(String)
    upvotes = Column(Integer)
    num_comments = Column(Integer)
    created_at = Column(DateTime)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # LLM analysis
    is_pain_point = Column(Integer, default=0)   # 0/1
    category = Column(String)
    urgency_score = Column(Float)
    problem_summary = Column(Text)
    solution_suggestion = Column(Text)
    analyzed = Column(Integer, default=0)         # 0/1

    # New columns
    favorite = Column(Integer, default=0)         # 0/1
    opportunity_score = Column(Float)             # composite score
    trending = Column(Integer, default=0)         # 0/1 flag


def init_db():
    Base.metadata.create_all(engine)
    # Migrate: add new columns if they don't exist (SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS)
    from sqlalchemy import inspect, text
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = {col["name"] for col in inspector.get_columns("painpoints")}
        migrations = [
            ("favorite",          "INTEGER DEFAULT 0"),
            ("opportunity_score", "REAL"),
            ("trending",          "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in migrations:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE painpoints ADD COLUMN {col_name} {col_def}"))
        conn.commit()
