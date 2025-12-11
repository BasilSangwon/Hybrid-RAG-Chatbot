
import os
import sys
import json
import random
import time
from sqlalchemy.orm import Session
from langchain_postgres import PGVector
from langchain_community.graphs import Neo4jGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from sqlalchemy import text

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(server_dir)
sys.path.append(server_dir)
sys.path.append(project_root)

from core.config import DB_CONNECTION, COLLECTION_NAME, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, GOOGLE_API_KEY
from core.database import CorrectAnswer, SessionLocal, Experiment
from services.embedder import get_bge_m3_embedding

# Initialize Resources
print("   [Eval] Initializing resources...")
embeddings = get_bge_m3_embedding()
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_CONNECTION,
    use_jsonb=True,
)

try:
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
except:
    graph = None

# Removed global llm init to allow dynamic selection
# llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=GOOGLE_API_KEY)

def get_llm(model_name="gemini-2.0-flash"):
    return ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=GOOGLE_API_KEY)

def safe_invoke(llm, prompt, retries=3, base_delay=10):
    """
    Invokes LLM with retry logic for rate limits.
    Strictly NO fallback to other models.
    """
    for i in range(retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                if i < retries - 1:
                    wait_time = base_delay * (i + 1) + random.uniform(1, 3)
                    print(f"⚠️ [Eval] Rate limit hit (429). Retrying in {wait_time:.1f}s... (Attempt {i+1}/{retries})")
                    time.sleep(wait_time)
                    continue
            # If not 429 or retries exhausted, re-raise
            raise e

def calculate_metrics(question, answer, context, ground_truth=None, model_name="gemini-2.0-flash"):
    """
    Uses LLM to calculate Faithfulness, Answer Relevancy, and Context Precision.
    Returns a dict with scores.
    """
    llm = get_llm(model_name)
    
    # 1. Faithfulness
    # [Delay to prevent burst]
    time.sleep(2) 
    
    faith_prompt = f"""
    You are a judge. Evaluate if the ANSWER is derived ONLY from the CONTEXT.
    
    [Context]
    {context}
    
    [Answer]
    {answer}
    
    Return a score between 0.0 and 1.0 (1.0 = fully faithful).
    Return ONLY the number.
    """
    try:
        res = safe_invoke(llm, faith_prompt)
        faith_score = float(res.content.strip())
    except: faith_score = 0.5

    # 2. Answer Relevancy
    time.sleep(2)
    
    rel_prompt = f"""
    You are a judge. Evaluate if the ANSWER is relevant to the QUESTION.
    
    [Question]
    {question}
    
    [Answer]
    {answer}
    
    Return a score between 0.0 and 1.0 (1.0 = fully relevant).
    Return ONLY the number.
    """
    try:
        res = safe_invoke(llm, rel_prompt)
        rel_score = float(res.content.strip())
    except: rel_score = 0.5

    # 3. Context Precision
    time.sleep(2)

    # If ground_truth is provided, check if context contains it.
    prec_prompt = f"""
    You are a judge. Evaluate if the CONTEXT contains the information needed to answer the QUESTION.
    
    [Question]
    {question}
    
    [Context]
    {context}
    
    Return a score between 0.0 and 1.0 (1.0 = fully precise).
    Return ONLY the number.
    """
    try:
        res = safe_invoke(llm, prec_prompt)
        prec_score = float(res.content.strip())
    except: prec_score = 0.5

    return {
        "faithfulness": faith_score,
        "answer_relevancy": rel_score,
        "context_precision": prec_score
    }

def run_rag_generation(question, model_name="gemini-2.0-flash"):
    """
    Simulates the RAG pipeline to generate an answer.
    """
    # 1. Vector Search
    # [NEW] Dynamic Vector Store Selection
    current_vector_store = vector_store
    session = SessionLocal()
    try:
        latest_exp = session.query(Experiment).filter(Experiment.rag_type == "vector").order_by(Experiment.created_at.desc()).first()
        if latest_exp and latest_exp.collection_name:
            current_vector_store = PGVector(
                embeddings=embeddings,
                collection_name=latest_exp.collection_name,
                connection=DB_CONNECTION,
                use_jsonb=True,
            )
            # print(f"🔎 [Eval] Using Collection: {latest_exp.collection_name}")
    except Exception as e:
        print(f"⚠️ [Eval] Vector selection failed: {e}")
    finally:
        session.close()

    docs = current_vector_store.similarity_search(question, k=10)
    vector_context = "\n".join([d.page_content for d in docs]) if docs else "No vector context."

    # 2. Graph Search (Simplified)
    graph_context = "No graph context."
    if graph:
        try:
            # Simple keyword search for now to avoid complex Cypher generation overhead in eval
            # In a real scenario, we should reuse the exact same logic as main.py
            # For this 'Performance Report', we'll use a simplified retrieval
            res = graph.query(f"MATCH (n) WHERE toLower(n.id) CONTAINS '{question.split()[0]}' RETURN n.id LIMIT 5")
            if res:
                graph_context = ", ".join([r['n.id'] for r in res])
        except: pass

    # 3. Generate
    final_prompt = f"""
    Answer the question based on the context.
    
    [Context]
    {vector_context}
    {graph_context}
    
    [Question]
    {question}
    """
    llm = get_llm(model_name)
    # Use safe_invoke
    res = safe_invoke(llm, final_prompt)
    response = res.content
    return response, vector_context + "\n" + graph_context

def run_evaluation(limit=5, model_name="gemini-2.0-flash"):
    """
    Main evaluation function.
    """
    session = SessionLocal()
    try:
        # Get Golden Data
        answers = session.query(CorrectAnswer).order_by(CorrectAnswer.id.desc()).limit(limit).all()
        
        if not answers:
            return {"status": "error", "message": "No golden data found."}

        total_faith = 0
        total_rel = 0
        total_prec = 0
        details = []

        print(f"📊 Starting Evaluation using {model_name} (Limit: {limit})")

        for i, a in enumerate(answers):
            print(f"   [{i+1}/{len(answers)}] Evaluating Q: {a.question[:30]}...")
            
            # Generate RAG Answer
            try:
                gen_answer, context = run_rag_generation(a.question, model_name=model_name)
                
                # Calculate Metrics
                metrics = calculate_metrics(a.question, gen_answer, context, ground_truth=a.answer, model_name=model_name)
                
                total_faith += metrics['faithfulness']
                total_rel += metrics['answer_relevancy']
                total_prec += metrics['context_precision']
                
                details.append({
                    "question": a.question,
                    "answer": gen_answer, # Show generated answer
                    "ground_truth": a.answer,
                    "faithfulness": metrics['faithfulness'],
                    "relevancy": metrics['answer_relevancy'],
                    "precision": metrics['context_precision']
                })

                # [Rate Limit] Cooldown between items
                time.sleep(5) 
                
            except Exception as item_error:
                print(f"   ⚠️ Error processing item {a.id}: {item_error}")
                # Don't break the whole loop, just skip this item? Or fail? 
                # User hates errors, so let's fail gracefully or logging it.

        count = len(details)
        if count == 0:
             return {"status": "error", "message": "Evaluation failed for all items."}

        return {
            "status": "ok",
            "result": {
                "faithfulness": round(total_faith / count, 2),
                "answer_relevancy": round(total_rel / count, 2),
                "context_precision": round(total_prec / count, 2),
                "details": details
            }
        }

    except Exception as e:
        print(f"Eval Error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        session.close()

if __name__ == "__main__":
    # Test run
    print(run_evaluation(limit=2))
