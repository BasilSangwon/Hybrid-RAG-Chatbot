from langchain_postgres import PGVector
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from sqlalchemy import text
from server.core.config import DB_CONNECTION, COLLECTION_NAME, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, GOOGLE_API_KEY
from server.core.database import engine
from server.services.embedder import get_bge_m3_embedding

# 1. Initialize Components
print("🚀 [Service] Initializing RAG components...")

# Embeddings
embeddings = get_bge_m3_embedding()

# Vector Store
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_CONNECTION,
    use_jsonb=True,
)

# LLMs
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    google_api_key=GOOGLE_API_KEY
)

llm_pro = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0,
    google_api_key=GOOGLE_API_KEY
)

# Graph
graph = None
graph_chain_flash = None
graph_chain_pro = None

try:
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD
    )
    graph_chain_flash = GraphCypherQAChain.from_llm(
        llm=llm_flash,
        graph=graph,
        verbose=True,
        allow_dangerous_requests=True
    )
    graph_chain_pro = GraphCypherQAChain.from_llm(
        llm=llm_pro,
        graph=graph,
        verbose=True,
        allow_dangerous_requests=True
    )
    print("   ✅ Neo4j Graph Connected!")
except Exception as e:
    print(f"   ⚠️ Neo4j Connection Failed: {e}")

# 2. Helper Functions

def check_correct_answer(query_vec, threshold=0.92):
    try:
        with engine.connect() as conn:
            sql = text("SELECT answer, 1 - (embedding <=> :vec) as score FROM correct_answers ORDER BY score DESC LIMIT 1")
            result = conn.execute(sql, {"vec": str(query_vec)}).fetchone()
            if result and result[1] >= threshold: return result[0]
    except: pass
    return None

def get_hybrid_docs(user_query, k=3):
    return vector_store.similarity_search(user_query, k=k)

def get_graph_context(user_query, model_type="flash"):
    chain = graph_chain_pro if model_type == "pro" else graph_chain_flash
    if not chain: return "그래프 DB 연결 안됨."
    try:
        response = chain.invoke({"query": user_query})
        return response.get("result", "관련 정보 없음")
    except Exception as e:
        print(f"Graph Search Error: {e}")
        return "그래프 검색 실패"
