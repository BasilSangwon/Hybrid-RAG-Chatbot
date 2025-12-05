import os
import time
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_neo4j import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
# OpenAI 사용 시 주석 해제
# from langchain_openai import ChatOpenAI 

from server.core.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, GOOGLE_API_KEY, RAW_DATA_DIR

def run_graph_ingest(model_name: str, experiment_id: int, chunk_size: int = 2000, overlap: int = 200, reset_db: bool = False):
    print(f"\n🕸️  [Graph Ingest] Start setup... Model: [{model_name}] | Exp ID: {experiment_id} | Chunk: {chunk_size} | Overlap: {overlap} | Reset: {reset_db}")

    # 1. Connect Neo4j
    try:
        graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        print("   ✅ Neo4j Connected!")
    except Exception as e:
        print(f"   ❌ Neo4j Connection Failed: {e}")
        return

    # 2. Reset DB (초기화 옵션)
    if reset_db:
        print("   🧹 Clearing existing Neo4j data (Reset Mode)...")
        try:
            graph.query("MATCH (n) DETACH DELETE n")
            print("   ✅ DB Fully Cleared.")
        except Exception as e:
            print(f"   ⚠️ DB Clear Failed: {e}")

    # 3. Prepare LLM (Dynamic Instantiation)
    llm = None
    if "gemini" in model_name.lower():
        llm = ChatGoogleGenerativeAI(
            model=model_name, 
            temperature=0,
            google_api_key=GOOGLE_API_KEY
        )
    elif "gpt" in model_name.lower():
        # OpenAI 사용 시
        # llm = ChatOpenAI(model=model_name, temperature=0)
        print(f"   ⚠️ OpenAI model selected ({model_name}). Make sure API key is set.")
        pass # 실제 구현 시 주석 해제
    else:
        print(f"   ⚠️ Unknown model '{model_name}', using default Gemini Flash.")
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=GOOGLE_API_KEY)
    
    # ---------------------------------------------------------
    # [핵심 수정] 스키마(Schema) 강제 정의 (Schema Enforcement)
    # ---------------------------------------------------------
    # LLM이 '생성', 'WITH' 같은 쓸모없는 관계를 만들지 못하게 막고,
    # 검색 프롬프트(main.py)와 일치하는 구조로만 데이터를 생성하게 합니다.
    
    allowed_nodes = [
        "Product",      # 제품 (Galaxy S25)
        "Feature",      # 기능 (실시간 통역)
        "Spec",         # 스펙 (4000mAh)
        "Requirement",  # 필요조건 (네트워크, 계정)
        "Component",    # 구성요소 (카메라, 배터리)
        "UserManual",   # 매뉴얼 문서
        "Section"       # 매뉴얼 섹션
    ]
    
    allowed_rels = [
        "HAS_FEATURE",      # 제품 -> 기능
        "HAS_SPEC",         # 제품 -> 스펙
        "REQUIRES",         # 기능 -> 조건 (네트워크 등)
        "INCLUDES",         # 포함 관계
        "PART_OF",          # 구성 관계
        "RELATED_TO",       # 일반적인 관련성
        "HAS_MANUAL",       # 제품 -> 매뉴얼
        "HAS_SECTION"       # 매뉴얼 -> 섹션
    ]

    llm_transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=allowed_nodes,
        allowed_relationships=allowed_rels,
        # node_properties=["id"] # id 속성은 기본적으로 생성됨
    )
    # ---------------------------------------------------------

    # 4. Load Files
    if not os.path.exists(RAW_DATA_DIR):
        print("   ❌ Data directory not found.")
        return

    files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.pdf')]
    if not files:
        print("   ❌ No PDF files found.")
        return

    # 5. Processing Loop
    for filename in files:
        print(f"\n📄 Processing '{filename}' using {model_name}... (Chunk: {chunk_size})")
        file_path = os.path.join(RAW_DATA_DIR, filename)
        
        loader = PyMuPDFLoader(file_path)
        raw_docs = loader.load()
        
        # Graph는 문맥 파악을 위해 Chunk Size를 넉넉하게 잡음
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        docs = text_splitter.split_documents(raw_docs)
        print(f"   -> {len(docs)} chunks created.")

        print("   ⏳ Extracting relationships & Tagging metadata...")
        BATCH_SIZE = 1 # API Rate Limit 고려
        
        for i in range(0, len(docs), BATCH_SIZE):
            batch_docs = docs[i : i + BATCH_SIZE]
            try:
                # (1) 그래프 문서 변환 (스키마에 맞춰 추출)
                graph_docs = llm_transformer.convert_to_graph_documents(batch_docs)
                
                # (2) 메타데이터 태깅 (모델명, 파일명)
                # 추출된 노드/관계에 출처 정보를 강제로 주입합니다.
                for g_doc in graph_docs:
                    for node in g_doc.nodes:
                        node.properties['source_model'] = model_name
                        node.properties['source_file'] = filename
                        if experiment_id:
                            node.properties['experiment_id'] = experiment_id
                        # id가 없는 경우 대비 (보통은 LLMGraphTransformer가 채워줌)
                        if 'id' not in node.properties:
                            node.properties['id'] = node.id 

                    for rel in g_doc.relationships:
                        rel.properties['source_model'] = model_name
                        if experiment_id:
                            rel.properties['experiment_id'] = experiment_id
                
                # (3) DB 저장
                graph.add_graph_documents(graph_docs)
                print(f"      📦 Batch {i//BATCH_SIZE + 1} saved.")
                time.sleep(1) # 휴식 (Rate Limit 방지)
                
            except Exception as e:
                print(f"      ⚠️ Error in batch {i}: {e}")

    print(f"\n🎉 [Success] Graph Ingestion Complete with [{model_name}]!")

# --- [2] [NEW] 특정 모델 데이터 삭제 함수 ---
def delete_graph_data(model_name: str):
    """
    선택한 모델(source_model)로 생성된 노드와 관계만 삭제합니다.
    """
    print(f"\n🗑️  [Graph Delete] Removing data for model: [{model_name}]")
    
    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
        
        # 해당 모델 태그가 붙은 노드와 관계를 모두 삭제하는 Cypher 쿼리
        query = f"""
        MATCH (n)
        WHERE n.source_model = '{model_name}'
        DETACH DELETE n
        """
        graph.query(query)
        print(f"   ✅ Successfully deleted nodes/rels for '{model_name}'")
        return True
    except Exception as e:
        print(f"   ❌ Delete Failed: {e}")
        return False

if __name__ == "__main__":
    # Test run
    run_graph_ingest(model_name="gemini-2.0-flash", experiment_id=0)