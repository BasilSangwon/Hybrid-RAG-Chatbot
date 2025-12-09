import os
import time
import pymupdf4llm
from langchain_core.documents import Document
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

    # 3. Prepare LLM (Dynamic Instantiation) - 사용자 선택 존중
    llm = None
    if "gemini" in model_name.lower():
        llm = ChatGoogleGenerativeAI(
            model=model_name,  # 사용자가 선택한 모델 그대로 사용
            temperature=0,
            google_api_key=GOOGLE_API_KEY
        )
    elif "gpt" in model_name.lower():
        # OpenAI 사용 시
        # llm = ChatOpenAI(model=model_name, temperature=0)
        print(f"   ⚠️ OpenAI model selected ({model_name}). Make sure API key is set.")
        pass 
    else:
        print(f"   ⚠️ Unknown model '{model_name}', using default Gemini Flash.")
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=GOOGLE_API_KEY)
    
    # ---------------------------------------------------------
    # 스키마(Schema) 정의
    # ---------------------------------------------------------
    allowed_nodes = [
        "Product", "Feature", "Spec", 
        "Requirement", "Constraint", "Condition", 
        "Component", "UserManual", "Section"
    ]
    
    allowed_rels = [
        "HAS_FEATURE", "HAS_SPEC", 
        "REQUIRES", "HAS_CONSTRAINT", "HAS_CONDITION",
        "INCLUDES", "PART_OF", "RELATED_TO", 
        "HAS_MANUAL", "HAS_SECTION"
    ]

    llm_transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=allowed_nodes,
        allowed_relationships=allowed_rels,
        node_properties=["name", "description"]
    )
    # ---------------------------------------------------------

    # 4. Load Files
    # DB에 이미 저장된 파일 목록을 가져옵니다. (main.py의 stats API 활용 로직 등을 참고하거나 직접 쿼리)
    try:
        existing_files = [r['source_file'] for r in graph.query("MATCH (n) WHERE n.source_model = $model RETURN DISTINCT n.source_file as source_file", {"model": model_name})]
    except:
        existing_files = []

    for filename in files:
        # [핵심] 이미 학습한 파일이면 건너뜁니다! (토큰 절약)
        if filename in existing_files:
            print(f"⏩ Skipping '{filename}' (Already ingested)")
            continue
            
        print(f"\n📄 Processing '{filename}'...")

    files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.pdf')]
    if not files:
        print("   ❌ No PDF files found.")
        return

    # 5. Processing Loop
    for filename in files:
        print(f"\n📄 Processing '{filename}' using {model_name}... (Chunk: {chunk_size})")
        file_path = os.path.join(RAW_DATA_DIR, filename)
        
        # [NEW] PyMuPDF4LLM Markdown Conversion
        try:
            print("   📄 Converting PDF to Markdown using pymupdf4llm...")
            md_text = pymupdf4llm.to_markdown(file_path)
            # Wrap in Document object
            raw_docs = [Document(page_content=md_text, metadata={"source": filename})]
            print("   ✅ Markdown conversion successful.")
        except Exception as e:
            print(f"   ⚠️ Markdown conversion failed: {e}. Fallback to standard loader.")
            loader = PyMuPDFLoader(file_path)
            raw_docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        docs = text_splitter.split_documents(raw_docs)
        print(f"   -> {len(docs)} chunks created.")

        print("   ⏳ Extracting relationships & Tagging metadata...")
        BATCH_SIZE = 1 
        
        for i in range(0, len(docs), BATCH_SIZE):
            batch_docs = docs[i : i + BATCH_SIZE]
            try:
                # (1) 그래프 문서 변환
                graph_docs = llm_transformer.convert_to_graph_documents(batch_docs)
                
                # (2) 메타데이터 태깅
                for g_doc in graph_docs:
                    for node in g_doc.nodes:
                        node.properties['source_model'] = model_name
                        node.properties['source_file'] = filename
                        
                        # [수정] 0번 ID도 저장되도록 조건 변경
                        if experiment_id is not None:
                            node.properties['experiment_id'] = experiment_id
                            
                        if 'name' not in node.properties:
                            node.properties['name'] = node.id 
                        
                        # [FIX] Remove 'id' property if it exists to avoid Neo4j reserved keyword error
                        if 'id' in node.properties:
                            del node.properties['id'] 

                    for rel in g_doc.relationships:
                        rel.properties['source_model'] = model_name
                        if experiment_id is not None:
                            rel.properties['experiment_id'] = experiment_id
                
                # (3) DB 저장
                graph.add_graph_documents(graph_docs)
                print(f"      📦 Batch {i//BATCH_SIZE + 1}/{len(docs)} saved.")
                
            except Exception as e:
                print(f"      ⚠️ Error in batch {i}: {e}")
            
            # [핵심 수정] 성공하든 실패하든 무조건 대기 (Rate Limit 방지)
            # try-except 밖으로 빼서 에러 발생 시 연속 호출 방지
            finally:
                print("      ⏳ Waiting 21s...") 
                time.sleep(21)

    print(f"\n🎉 [Success] Graph Ingestion Complete with [{model_name}]!")

# --- 삭제 함수는 기존 유지 ---
def delete_graph_data(model_name: str):
    print(f"\n🗑️  [Graph Delete] Removing data for model: [{model_name}]")
    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
        query = f"MATCH (n) WHERE n.source_model = '{model_name}' DETACH DELETE n"
        graph.query(query)
        print(f"   ✅ Successfully deleted nodes/rels for '{model_name}'")
        return True
    except Exception as e:
        print(f"   ❌ Delete Failed: {e}")
        return False

if __name__ == "__main__":
    run_graph_ingest(model_name="gemini-2.0-flash", experiment_id=0)