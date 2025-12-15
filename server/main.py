import os
import sys
import uvicorn
import warnings
import google.generativeai as genai  # [필수] pip install google-generativeai

# 경고 숨기기
warnings.filterwarnings("ignore")

from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text, func
from sqlalchemy.orm import Session

# LangChain Logic
from langchain_postgres import PGVector
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate

# [MONKEY PATCH] Google API 'thinking' argument error fix
try:
    import google.generativeai.types.model_types as model_types
    original_init = model_types.Model.__init__

    def new_init(self, **kwargs):
        # 'thinking' argument causing TypeError in v0.8.5
        if 'thinking' in kwargs:
            kwargs.pop('thinking')
        original_init(self, **kwargs)

    model_types.Model.__init__ = new_init
    print("✅ Applied monkey patch for Google API 'thinking' argument.")
except Exception as e:
    print(f"⚠️ Failed to apply monkey patch: {e}")

# Internal Modules (폴더 구조 변경 반영)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
# server 폴더와 project root를 path에 추가
sys.path.append(current_dir)
sys.path.append(project_root)

from core.config import DB_CONNECTION, COLLECTION_NAME, RAW_DATA_DIR, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, GOOGLE_API_KEY

# [CRITICAL] Configure Google API Key for genai.list_models()
genai.configure(api_key=GOOGLE_API_KEY)
from core.database import SessionLocal, engine, Persona, Feedback, CorrectAnswer, TokenUsage, Experiment, init_db, get_db
import uuid
from datetime import datetime
from core.schemas import PersonaReq, AnswerReq, FeedbackReq, ChatReq, GenerateQAReq, IngestReq
from services.embedder import get_bge_m3_embedding
from services.cost_calculator import calculate_cost, PRICING_MAP
from pipelines.ingest_vec import run_ingest as run_vector_ingest
from pipelines.ingest_graph import run_graph_ingest
from pipelines.qa_gen import generate_bulk_qa



# --- 초기화 ---
print("🚀 [Server] Initializing Hybrid RAG System...")

# DB Init
init_db()

# Vector Store 연결
embeddings = get_bge_m3_embedding()
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_CONNECTION,
    use_jsonb=True,
)

# Neo4j Graph 연결 확인
try:
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    print("   ✅ Neo4j Graph Connected!")
    
    # [FIX] Register property keys to prevent 'UnknownPropertyKeyWarning' in empty DB
    try:
        print("   🔧 Registering graph property keys...")
        graph.query("CREATE (n:_SchemaRegistration {source_model: 'init', source_file: 'init', experiment_id: 0}) DELETE n")
    except Exception as e:
        print(f"   ⚠️ Failed to register property keys: {e}")

except Exception as e:
    print(f"   ⚠️ Neo4j Connection Failed: {e}")
    graph = None

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Static Files ---
app.mount("/js", StaticFiles(directory=os.path.join(os.path.dirname(current_dir), "client", "js")), name="js")
# app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(current_dir), "client", "static")), name="static")

# --- Job Status Management ---
JOB_STATUS = {"vector": "idle", "graph": "idle"}

@app.get("/api/job_status")
def get_job_status():
    return JOB_STATUS

def background_ingest_task(type: str, exp_id: int, config: dict, collection_name: str = None, **kwargs):
    global JOB_STATUS
    JOB_STATUS[type] = "running"
    try:
        if type == "vector":
            chunk_size = kwargs.get("chunk_size", 1000)
            overlap = kwargs.get("overlap", 100)
            run_vector_ingest(collection_name=collection_name, chunk_size=chunk_size, overlap=overlap)
        elif type == "graph":
            model_name = kwargs.get("model_name", "gemini-2.0-flash")
            reset_db = kwargs.get("reset_db", False)
            chunk_size = kwargs.get("chunk_size", 2000)
            overlap = kwargs.get("overlap", 200)
            run_graph_ingest(model_name=model_name, experiment_id=exp_id, chunk_size=chunk_size, overlap=overlap, reset_db=reset_db)
    except Exception as e:
        print(f"Ingest Error ({type}): {e}")
    finally:
        JOB_STATUS[type] = "idle"
class QAGenRequest(BaseModel):
    filename: str
    model: str = "gemini-2.0-flash"

@app.post("/api/generate_qa")
async def generate_qa_endpoint(req: QAGenRequest, background_tasks: BackgroundTasks):
    from server.pipelines.qa_gen import generate_bulk_qa
    # Pass model to the pipeline
    background_tasks.add_task(generate_bulk_qa, filename=req.filename, model_name=req.model)
    return {"status": "ok", "message": f"Background QA generation started using {req.model}."}

class EvaluationRequest(BaseModel):
    limit: int = 5
    model: str = "gemini-2.0-flash"

@app.post("/api/ingest")
async def run_ingest(req: IngestReq, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    global JOB_STATUS
    
    # Auto-generate name if empty
    if not req.name or req.name.strip() == "":
        timestamp = datetime.now().strftime("%y%m%d_%H%M")
        
        if req.type == "vector":
            chunk_size = req.config.get("chunk_size", 1000)
            overlap = req.config.get("chunk_overlap", 100)
            req.name = f"Vec_C{chunk_size}_O{overlap}_{timestamp}"
            
        elif req.type == "graph":
            # [변경된 부분] Graph 실험 이름 생성 규칙 적용
            # Format: Graph_{ModelName}_c{ChunkSize}_o{Overlap}_{YYMMDD_HHMM}
            
            model_name = req.config.get("llm_model", "unknown")
            chunk_size = req.config.get("chunk_size", 0)
            # admin.html에서 payload로 chunk_overlap을 보냅니다.
            overlap = req.config.get("chunk_overlap", req.config.get("overlap", 0))
            
            req.name = f"Graph_{model_name}_c{chunk_size}_o{overlap}_{timestamp}"

    # Check if name exists
    existing = db.query(Experiment).filter(Experiment.name == req.name).first()
    if existing:
        # If auto-generated name exists, append seconds to make it unique
        if not req.name or req.name.strip() == "":
             req.name = f"{req.name}_{datetime.now().strftime('%S')}"
        else:
             return {"status": "error", "message": f"Experiment name '{req.name}' already exists."}

    if JOB_STATUS.get(req.type) == "running":
        return {"status": "error", "message": f"{req.type} ingestion is already running."}
    
    # 1. Create Experiment Record
    experiment = Experiment(
        name=req.name,
        rag_type=req.type,
        config=req.config,
        collection_name=None 
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    
    # 2. Prepare Data & Update Experiment
    collection_name = None
    if req.type == "vector":
        collection_name = f"vec_exp_{experiment.id}"
        experiment.collection_name = collection_name
        db.commit()
    
    # 3. Extract Config & Trigger Background Task
    default_chunk = 1000 if req.type == "vector" else 2000
    default_overlap = 100 if req.type == "vector" else 200
    
    chunk_size = int(req.config.get("chunk_size", default_chunk))
    overlap = int(req.config.get("chunk_overlap", req.config.get("overlap", default_overlap)))
    
    task_kwargs = {
        "chunk_size": chunk_size,
        "overlap": overlap
    }

    if req.type == "graph":
        task_kwargs["model_name"] = req.config.get("llm_model", "gemini-2.0-flash")
        task_kwargs["reset_db"] = req.config.get("reset_db", False)

    background_tasks.add_task(
        background_ingest_task, 
        req.type, 
        exp_id=experiment.id, 
        config=req.config, 
        collection_name=collection_name,
        **task_kwargs
    )
    
    return {
        "status": "ok", 
        "message": f"{req.type} ingestion started (Exp ID: {experiment.id}, Name: {req.name}).", 
        "exp_id": experiment.id,
        "collection_name": collection_name,
        "name": req.name
    }

@app.delete("/api/vector_store")
def reset_vector_store():
    try:
        with engine.connect() as conn:
            # Truncate langchain_pg_embedding table
            conn.execute(text("""
                DELETE FROM langchain_pg_embedding 
                WHERE collection_id IN (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """), {"name": COLLECTION_NAME})
            conn.commit()
        return {"status": "ok", "message": "Vector store reset."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/files/{filename}")
def delete_file(filename: str):
    file_path = os.path.join(RAW_DATA_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "ok", "message": f"File {filename} deleted."}
    return {"status": "error", "message": "File not found."}

# --- Basic Data Management APIs ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/personas")
def get_personas(db: Session = Depends(get_db)):
    return db.query(Persona).all()

@app.post("/api/personas")
def create_persona(req: PersonaReq, db: Session = Depends(get_db)):
    p = Persona(name=req.name, system_prompt=req.system_prompt)
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.post("/api/personas/{id}/activate")
def activate_persona(id: int, db: Session = Depends(get_db)):
    db.query(Persona).update({Persona.active: False})
    db.query(Persona).filter(Persona.id == id).update({Persona.active: True})
    db.commit()
    return {"status": "ok"}

@app.get("/api/files")
def list_files():
    if not os.path.exists(RAW_DATA_DIR): return []
    return [f for f in os.listdir(RAW_DATA_DIR) if f.endswith(".pdf")]

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(RAW_DATA_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename}

@app.get("/api/answers")
def get_answers(db: Session = Depends(get_db)):
    # [UPDATED] Sort by ID descending as requested
    return db.query(CorrectAnswer).order_by(CorrectAnswer.id.desc()).all()

@app.post("/api/answers")
def add_answer(req: AnswerReq, db: Session = Depends(get_db)):
    vec = embeddings.embed_query(req.question)
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO correct_answers (question, answer, embedding) VALUES (:q, :a, :v)"),
                     {"q": req.question, "a": req.answer, "v": str(vec)})
        conn.commit()
    return {"status": "ok"}

@app.delete("/api/answers/{id}")
def delete_answer(id: int, db: Session = Depends(get_db)):
    db.query(CorrectAnswer).filter(CorrectAnswer.id == id).delete()
    db.commit()
    return {"status": "ok"}

@app.delete("/api/answers_all")
def delete_all_answers(db: Session = Depends(get_db)):
    count = db.query(CorrectAnswer).delete()
    db.commit()
    return {"status": "ok", "message": f"{count}개 항목 삭제됨"}

@app.get("/api/feedback")
def get_feedback(db: Session = Depends(get_db)):
    return db.query(Feedback).all()

@app.post("/api/feedback")
def add_feedback(req: FeedbackReq, db: Session = Depends(get_db)):
    f = Feedback(context=req.context, guideline=req.guideline)
    db.add(f); db.commit()
    return f

@app.delete("/api/feedback/{id}")
def delete_feedback(id: int, db: Session = Depends(get_db)):
    db.query(Feedback).filter(Feedback.id == id).delete()
    db.commit()
    return {"status": "ok"}

# [UPDATED] Dynamic Model List
@app.get("/api/models")
def get_models():
    """
    Fetch all Gemini models that support generateContent.
    """
    try:
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                # Exclude vision/audio/legacy/beta if needed, but user asked for "ALL"
                # We'll filter out non-gemini or very old ones if desired, but let's keep it broad for now.
                if "gemini" in name: 
                    models.append({
                        "id": name,
                        "display_name": name
                    })
        return models
    except Exception as e:
        print(f"Error fetching models: {e}")
        # Fallback list (Only 2.0+)
        return [
            {"id": "gemini-2.0-flash", "display_name": "gemini-2.0-flash"},
            {"id": "gemini-2.0-flash-exp", "display_name": "gemini-2.0-flash-exp"},
            {"id": "gemini-2.5-computer-use-preview-10-2025", "display_name": "gemini-2.5-preview"}
        ]

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    # Calculate total cost and tokens
    total_cost = db.query(func.sum(TokenUsage.cost_usd)).scalar() or 0.0
    total_input = db.query(func.sum(TokenUsage.input_tokens)).scalar() or 0
    total_output = db.query(func.sum(TokenUsage.output_tokens)).scalar() or 0
    
    # Fetch all experiments
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    
    vector_exps = []
    graph_exps = []
    
    # Global counts (Direct DB Query for Total)
    total_vector_count = 0
    try:
        with engine.connect() as conn:
            # Count ALL embeddings regardless of collection/experiment
            total_vector_count = conn.execute(text("SELECT count(*) FROM langchain_pg_embedding")).scalar()
    except: total_vector_count = 0

    total_graph_count = 0
    if graph:
        try:
            # Count ALL nodes regardless of experiment
            res = graph.query("MATCH (n) RETURN count(n) AS count")
            if res: total_graph_count = res[0]["count"]
        except: total_graph_count = 0

    # Experiment Breakdown
    for exp in experiments:
        count = 0
        if exp.rag_type == "vector":
            if exp.collection_name:
                try:
                    with engine.connect() as conn:
                        sql = text("""
                            SELECT count(*) 
                            FROM langchain_pg_embedding e 
                            JOIN langchain_pg_collection c ON e.collection_id = c.uuid 
                            WHERE c.name = :name
                        """)
                        count = conn.execute(sql, {"name": exp.collection_name}).scalar()
                except: count = 0
            
            vector_exps.append({
                "id": exp.id,
                "name": exp.name,
                "chunk_size": exp.config.get("chunk_size"),
                "overlap": exp.config.get("chunk_overlap") or exp.config.get("overlap"),
                "created_at": exp.created_at.strftime("%Y-%m-%d %H:%M"),
                "count": count
            })

        elif exp.rag_type == "graph":
            if graph:
                try:
                    # Count nodes with this experiment_id
                    res = graph.query(f"MATCH (n) WHERE n.experiment_id = {exp.id} RETURN count(n) AS count")
                    if res: count = res[0]["count"]
                except: count = 0
            
            graph_exps.append({
                "id": exp.id,
                "name": exp.name,
                "model": exp.config.get("llm_model"),
                "chunk_size": exp.config.get("chunk_size"),
                "overlap": exp.config.get("chunk_overlap") or exp.config.get("overlap"),
                "created_at": exp.created_at.strftime("%Y-%m-%d %H:%M"),
                "count": count
            })
    
    # Graph Details (Model breakdown) - Restore for backward compatibility if needed, 
    # but for now we just return the new structure + totals
    graph_details = []
    if graph:
        try:
             res_breakdown = graph.query("""
                MATCH (n) 
                WHERE n.source_model IS NOT NULL 
                RETURN n.source_model AS model, count(n) AS count, collect(distinct n.source_file) AS files
                ORDER BY count DESC
            """)
             if res_breakdown:
                graph_details = [{"model": r["model"], "count": r["count"], "files": r["files"]} for r in res_breakdown]
        except: pass

    return {
        "total_cost": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "vector_count": total_vector_count,
        "graph_count": total_graph_count,
        "vector_experiments": vector_exps,
        "graph_experiments": graph_exps,
        "graph_details": graph_details
    }

@app.get("/api/experiments")
def get_experiments(db: Session = Depends(get_db)):
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    
    vector_exps = []
    graph_exps = []

    for exp in experiments:
        count = 0
        if exp.rag_type == "vector":
            if exp.collection_name:
                try:
                    with engine.connect() as conn:
                        sql = text("""
                            SELECT count(*) 
                            FROM langchain_pg_embedding e 
                            JOIN langchain_pg_collection c ON e.collection_id = c.uuid 
                            WHERE c.name = :name
                        """)
                        count = conn.execute(sql, {"name": exp.collection_name}).scalar()
                except: count = 0
            
            vector_exps.append({
                "id": exp.id,
                "name": exp.name,
                "date": exp.created_at.strftime("%Y-%m-%d %H:%M"),
                "config": exp.config,
                "count": count
            })

        elif exp.rag_type == "graph":
            if graph:
                try:
                    res = graph.query(f"MATCH (n) WHERE n.experiment_id = {exp.id} RETURN count(n) AS count")
                    if res: count = res[0]["count"]
                except: count = 0
            
            graph_exps.append({
                "id": exp.id,
                "name": exp.name,
                "date": exp.created_at.strftime("%Y-%m-%d %H:%M"),
                "config": exp.config,
                "count": count
            })

    return {
        "vector": vector_exps,
        "graph": graph_exps
    }

@app.delete("/api/experiments/{experiment_id}")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    # 1. Find Experiment
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"status": "error", "message": "Experiment not found"}

    try:
        # 2. Delete Data based on Type
        if exp.rag_type == "vector":
            if exp.collection_name:
                # Delete Collection (Cascade deletes embeddings)
                with engine.connect() as conn:
                    # Find collection UUID
                    res = conn.execute(text("SELECT uuid FROM langchain_pg_collection WHERE name = :name"), {"name": exp.collection_name}).fetchone()
                    if res:
                        collection_uuid = res[0]
                        # Delete embeddings
                        conn.execute(text("DELETE FROM langchain_pg_embedding WHERE collection_id = :uuid"), {"uuid": collection_uuid})
                        # Delete collection
                        conn.execute(text("DELETE FROM langchain_pg_collection WHERE uuid = :uuid"), {"uuid": collection_uuid})
                        conn.commit()
        
        elif exp.rag_type == "graph":
            if graph:
                # Delete nodes with this experiment_id
                graph.query(f"MATCH (n) WHERE n.experiment_id = {experiment_id} DETACH DELETE n")

        # 3. Delete Experiment Record
        db.delete(exp)
        db.commit()
        
        return {"status": "ok", "message": f"Experiment '{exp.name}' deleted."}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

# Legacy endpoint - keep for now or remove if unused
@app.delete("/api/graph/model/{model_name}")
def delete_graph_model_data(model_name: str):
    if not graph:
        return {"status": "error", "message": "Graph DB not connected"}
    
    try:
        from pipelines.ingest_graph import delete_graph_data
        success = delete_graph_data(model_name)
        if success:
            return {"status": "ok", "message": f"Data for {model_name} deleted."}
        else:
            return {"status": "error", "message": "Deletion failed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/usage")
def get_usage(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(TokenUsage).order_by(TokenUsage.timestamp.desc()).limit(limit).all()


@app.post("/api/evaluate")
async def api_evaluate(req: EvaluationRequest):
    """
    Run RAGAS evaluation on recent X items.
    """
    try:
        from pipelines.evaluate import run_evaluation
        # Pass the selected model to the evaluation function
        results = run_evaluation(limit=req.limit, model_name=req.model)
        if results["status"] == "error":
            raise HTTPException(status_code=500, detail=results["message"])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- [UPDATED] Hybrid Chat Endpoint ---
@app.post("/chat")
async def chat_endpoint(req: ChatReq, db: Session = Depends(get_db)):
    user_query = req.question
    
    # [핵심] 클라이언트가 선택한 모델로 LLM 인스턴스 즉시 생성 (Real-time Switching)
    try:
        chat_llm = ChatGoogleGenerativeAI(
            model=req.model, 
            temperature=0, 
            google_api_key=GOOGLE_API_KEY
        )
    except Exception as e:
        print(f"Model Init Error: {e}, fallback to default.")
        chat_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, google_api_key=GOOGLE_API_KEY)

    # Active Persona Check
    active_persona = db.query(Persona).filter(Persona.active == True).first()
    system_prompt_text = active_persona.system_prompt if active_persona else "You are a helpful AI assistant."

    async def gen():
        try:
            # [NEW] 동적 Vector Store 연결 (가장 최근 실험 찾기)
            current_vector_store = vector_store 
            
            latest_exp = db.query(Experiment).filter(Experiment.rag_type == "vector").order_by(Experiment.created_at.desc()).first()
            
            if latest_exp and latest_exp.collection_name:
                current_vector_store = PGVector(
                    embeddings=embeddings,
                    collection_name=latest_exp.collection_name,
                    connection=DB_CONNECTION,
                    use_jsonb=True,
                )
                print(f"🔎 Searching in Collection: {latest_exp.collection_name}")

            # 2. 정답 캐시 확인
            query_vec = embeddings.embed_query(user_query)
            try:
                with engine.connect() as conn:
                    sql = text("SELECT answer, 1 - (embedding <=> :vec) as score FROM correct_answers ORDER BY score DESC LIMIT 1")
                    result = conn.execute(sql, {"vec": str(query_vec)}).fetchone()
                    if result and result[1] >= 0.92:
                        yield f"⚡ {result[0]}"
                        return
            except: pass

            vector_context = "Not used"
            graph_context = "Not used"
            
            # 3. Vector Search
            if req.rag_type in ["hybrid", "vector"]:
                docs = current_vector_store.similarity_search(user_query, k=10)
                if docs:
                    vector_context = "\n".join([d.page_content[:500] for d in docs])
                else:
                    vector_context = "No relevant documents found."

            # 3. Graph Search
            if req.rag_type in ["hybrid", "graph"] and graph:
                # [수정 1] "Analyzing Knowledge Graph..." 메시지 전송 코드 삭제함
                # yield "🔍 Analyzing Knowledge Graph...\\n\\n" 
                
                try:
                    # [Dynamic Filtering Logic]
                    filter_condition = "" 
                    
                    CYPHER_GENERATION_TEMPLATE = f"""
                    You are a Neo4j Cypher expert.
                    The user asks a question regarding specific entities and their relationships.
                    
                    [Schema Info]
                    - Node Labels: `Product`, `Feature`, `Spec`, `Requirement`, `Component`, `UserManual`, `Section`
                    - Relationship Types: `HAS_FEATURE`, `HAS_SPEC`, `REQUIRES`, `INCLUDES`, `PART_OF`, `RELATED_TO`
                    - Node Properties: `name` (text content), `source_model`
                    
                    [CRITICAL INSTRUCTION]
                    1. Identify KEY ENTITIES from the question (e.g., '실시간 통역', '네트워크').
                    2. Map user intent to Schema:
                       - "Constraints", "Conditions", "Requirements", "제약", "조건" -> Look for `(:Requirement)` nodes or `[:REQUIRES]` relationships.
                       - "Features", "Functions" -> Look for `(:Feature)` nodes.
                    3. Use `toLower(n.name) CONTAINS` for partial matching of entity names.
                    4. **CRITICAL**: You MUST start every MATCH clause with `MATCH path = ...` to define the `path` variable.
                    
                    [Query Logic Strategy]
                    // Strategy 1: Path between two specific keywords
                    MATCH (start), (end)
                    WHERE toLower(start.name) CONTAINS 'keyword1' AND toLower(end.name) CONTAINS 'keyword2'
                    MATCH path = (start)-[*1..3]-(end)
                    RETURN path LIMIT 20
                    UNION
                    // Strategy 2: Neighbors of keywords
                    MATCH path = (n)-[r]-(m)
                    WHERE (toLower(n.name) CONTAINS 'keyword1' OR toLower(n.name) CONTAINS 'keyword2')
                    {filter_condition}
                    RETURN path LIMIT 50
                    
                    [Example]
                    Question: "실시간 통역의 제약 조건은?"
                    Cypher:
                    MATCH path = (n)-[:REQUIRES]-(m)
                    WHERE toLower(n.name) CONTAINS '실시간'
                    {filter_condition}
                    RETURN path LIMIT 20
                    UNION
                    MATCH path = (n)-[r]-(m)
                    WHERE toLower(n.name) CONTAINS '실시간'
                    {filter_condition}
                    RETURN path LIMIT 50
                    
                    7. The question is:
                    {{question}}
                    
                    8. Cypher Query:
                    """
                    
                    CYPHER_PROMPT = PromptTemplate(
                        input_variables=["schema", "question"], 
                        template=CYPHER_GENERATION_TEMPLATE
                    )

                    chain = GraphCypherQAChain.from_llm(
                        llm=chat_llm, 
                        graph=graph, 
                        verbose=True, 
                        allow_dangerous_requests=True,
                        cypher_prompt=CYPHER_PROMPT
                    )
                    res = chain.invoke({"query": user_query})
                    print(f"🔍 Generated Cypher Result: {res}")
                    graph_context = res.get("result", "No info in graph.")
                except Exception as e:
                    print(f"Graph Error: {e}")
                    graph_context = "Graph search failed."

            # 4. Final Prompt
            final_prompt = f"""
            {system_prompt_text}
            
            [Context - Vector DB]
            {vector_context}
            
            [Context - Knowledge Graph (Source Model: {req.model})]
            {graph_context}
            
            [User Question]
            {user_query}
            
            [Instructions for Answering]
            1. Answer the question specifically based on the provided contexts.
            2. **Format**: Use **Markdown** to improve readability.
               - Use **Bold** for key entities or conclusions.
               - Use bullet points (-) for listing details or evidence.
            3. If the context does not contain the answer, say you don't know.
            4. Respond in Korean.
            """

            # 5. Generate Stream
            full_response = ""
            async for chunk in chat_llm.astream(final_prompt):
                full_response += chunk.content
                yield chunk.content
            
            # 6. Debug Info
            # [수정 2] 줄바꿈 문자를 \\n (문자열)에서 \n (실제 줄바꿈)으로 변경
            debug_info = f"\n\n---\n**📊 Debug Info:**\n- **Model:** {req.model}\n- **Type:** {req.rag_type}\n- **Graph:** {graph_context}\n- **Vector:** {vector_context[:100]}..."
            yield debug_info

            # [NEW] Token Usage Tracking
            try:
                input_tokens = chat_llm.get_num_tokens(final_prompt)
                output_tokens = chat_llm.get_num_tokens(full_response)
                cost = calculate_cost(req.model, input_tokens, output_tokens)
                
                with SessionLocal() as db_log:
                    usage = TokenUsage(
                        session_id=req.session_id,
                        model_name=req.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost
                    )
                    db_log.add(usage)
                    db_log.commit()
            except Exception as e:
                print(f"⚠️ Token tracking failed: {e}")

        except Exception as e:
            print(f"Error in generation: {e}")
            yield f"System Error: {e}"

    return StreamingResponse(gen(), media_type="text/plain")

# --- Static Files ---
@app.get("/")
def serve_chat():
    # 경로 조정: server/main.py 위치 기준 상위 폴더의 client
    path = os.path.join(os.path.dirname(current_dir), "client", "index.html")
    return FileResponse(path)

@app.get("/admin")
def serve_admin():
    path = os.path.join(os.path.dirname(current_dir), "client", "admin.html")
    return FileResponse(path)

if __name__ == "__main__":
    print("📡 Server started at http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
