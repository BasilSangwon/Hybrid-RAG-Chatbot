from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, TIMESTAMP, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import text, func
from server.core.config import DB_CONNECTION

from sqlalchemy.dialects.postgresql import JSONB

# SQLAlchemy Setup
engine = create_engine(DB_CONNECTION)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Persona(Base):
    __tablename__ = "personas"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    system_prompt = Column(Text)
    active = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    context = Column(String)
    guideline = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

class CorrectAnswer(Base):
    __tablename__ = "correct_answers"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    # embedding column is handled by pgvector extension, usually defined manually or via specific types if available
    # For simplicity in ORM, we might skip mapping it directly if we use raw SQL for vector ops,
    # or use mapped_column with Vector type if langchain_postgres provides it.
    # Here we keep it simple and use raw SQL for vector operations as before.
    created_at = Column(TIMESTAMP, server_default=func.now())

class TokenUsage(Base):
    __tablename__ = "token_usage"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(TIMESTAMP, server_default=func.now())
    session_id = Column(String, index=True, nullable=True)
    model_name = Column(String, index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    rag_type = Column(String)       # 'vector', 'graph'
    config = Column(JSONB)          # 설정값 (Chunk size 등)
    result = Column(JSONB, nullable=True) # 점수 (RAGAS 등)
    collection_name = Column(String, unique=True, nullable=True) 
    
    created_at = Column(TIMESTAMP, server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    print("🛠️ [DB] Initializing database tables...")
    try:
        with engine.connect() as conn:
            # Enable Extensions
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_bigm"))
            conn.commit()
            
        # Create Tables (SQLAlchemy)
        Base.metadata.create_all(bind=engine)
        
        # Additional Raw SQL for Vector columns and Indexes (if not handled by ORM)
        with engine.connect() as conn:
            # Correct Answers Vector Column
            conn.execute(text("ALTER TABLE correct_answers ADD COLUMN IF NOT EXISTS embedding vector(1024)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_correct_answers_embedding ON correct_answers USING ivfflat (embedding vector_cosine_ops)"))
            
            # Feedback Vector Column (Optional, for future use)
            conn.execute(text("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS embedding vector(1024)"))
            
            # Default Persona
            conn.execute(text("""
                INSERT INTO personas (name, system_prompt, active) 
                VALUES ('기본 상담원', '당신은 제품 매뉴얼을 기반으로 답변하는 친절한 AI 상담원입니다.', TRUE)
                ON CONFLICT (name) DO NOTHING
            """))
            conn.commit()
            
        print("   ✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
