from pydantic import BaseModel
from typing import Optional, Dict, Any

class PersonaReq(BaseModel):
    name: str
    system_prompt: str

class AnswerReq(BaseModel):
    question: str
    answer: str

class FeedbackReq(BaseModel):
    context: str
    guideline: str

class ChatReq(BaseModel):
    question: str
    model: str
    rag_type: str
    session_id: Optional[str] = None
    graph_source: Optional[str] = "all"

class GenerateQAReq(BaseModel):
    filename: str  # 파일명을 받도록 수정

class IngestReq(BaseModel):
    type: str  # 'vector' or 'graph'
    name: str  # Experiment Name
    config: Dict[str, Any] # Flexible config (chunk_size, model, etc.)
