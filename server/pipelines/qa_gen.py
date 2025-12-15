import os
import json
import time
import threading
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from sqlalchemy import text

from server.core.config import RAW_DATA_DIR, GOOGLE_API_KEY
from server.core.database import engine
from server.services.embedder import get_bge_m3_embedding

# --- Prompt Template ---
def get_prompt_template(count_per_chunk=5):
    """Return prompt template with placeholders"""
    return f"""
Analyze the document chunk below and generate {count_per_chunk} pairs of Question and Answer.

[Document Chunk]
{{context}}

[Rules]
1. **Analyze the language of the document completely.** (Most likely Korean)
2. Generate questions and answers in the **SAME language** as the document.
3. Diverse questions (How-to, Troubleshooting, Specs, Features).
4. Answers MUST be based ONLY on the provided chunk.
5. Output strictly in JSON list format.
6. If the chunk doesn't have enough useful content, generate fewer Q&As.

[Example Output]
[
    {{"q": "배터리 교체 방법이 무엇인가요?", "a": "후면 커버를 열고..."}},
    {{"q": "초기화 방법", "a": "설정 > 일반 > 초기화 메뉴 진입"}}
]
"""

def get_prompt_fixed_length(count_per_chunk=5):
    """Return fixed part of prompt (excluding context) character count"""
    template = get_prompt_template(count_per_chunk)
    fixed_part = template.replace("{context}", "")
    return len(fixed_part)

# --- Main Generation Function ---
def generate_bulk_qa(filename=None, model_name="gemini-2.0-flash", count=10, chunk_size=5000, chunk_overlap=500, cancel_event=None):
    """
    Chunk-based Q&A generation to cover entire document.
    
    Args:
        filename: Target PDF file
        model_name: LLM model to use
        count: Total Q&A pairs to generate
        chunk_size: Characters per chunk (default 5000)
        chunk_overlap: Overlap between chunks (default 500)
        cancel_event: threading.Event for cancellation signal
    """
    
    # Helper function to check cancellation
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()
    
    print(f"🤖 [Auto QA] Generating {count} Q&A from PDFs using {model_name}...")
    print(f"   📊 Chunk Size: {chunk_size} chars | Overlap: {chunk_overlap} chars")
    
    # Check cancel at start
    if is_cancelled():
        print("❌ [Auto QA] Cancelled before start.")
        return
    
    # 1. Prepare Components
    embeddings = get_bge_m3_embedding()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY
    )

    # 2. Check Files
    if filename:
        target_files = [filename]
    else:
        target_files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.pdf')]
        
    if not target_files:
        print("❌ No PDF files found.")
        return

    total_added = 0

    for fname in target_files:
        # Check cancel before each file
        if is_cancelled():
            print("🛑 [Auto QA] Cancelled by user.")
            return
            
        print(f"\n📄 Processing '{fname}'...")
        file_path = os.path.join(RAW_DATA_DIR, fname)
        
        # Load and split document into chunks
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
        full_text = "\n".join([d.page_content for d in docs])
        
        print(f"   📏 Total document length: {len(full_text):,} chars")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(full_text)
        
        print(f"   📦 Split into {len(chunks)} chunks")
        
        # Calculate Q&A per chunk
        qa_per_chunk = max(1, count // len(chunks)) if chunks else count
        remaining_qa = count
        
        print(f"   🎯 Target: ~{qa_per_chunk} Q&A per chunk (Total: {count})")
        
        file_qa_count = 0
        
        for chunk_idx, chunk in enumerate(chunks):
            # Check cancel before each chunk
            if is_cancelled():
                print("🛑 [Auto QA] Cancelled by user.")
                return
            
            # Stop if we've generated enough
            if file_qa_count >= count:
                print(f"   ✅ Reached target {count} Q&A pairs.")
                break
            
            # Adjust Q&A count for last chunks
            current_target = min(qa_per_chunk, remaining_qa)
            if current_target <= 0:
                break
                
            print(f"\n   📝 Chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk):,} chars) - Target: {current_target} Q&A")
            
            prompt = get_prompt_template(current_target).replace("{context}", chunk)
            
            # Rate Limiting Sleep with cancel check (15 seconds)
            print("      💤 Cooling down (15s)...")
            for _ in range(15):
                if is_cancelled():
                    print("🛑 [Auto QA] Cancelled by user.")
                    return
                time.sleep(1)
            
            # API Call with Retry
            qa_list = []
            max_retries = 3
            
            for attempt in range(max_retries):
                if is_cancelled():
                    print("🛑 [Auto QA] Cancelled by user.")
                    return
                    
                try:
                    msg = [HumanMessage(content=prompt)]
                    res = llm.invoke(msg).content
                    
                    clean_json = res.replace("```json", "").replace("```", "").strip()
                    qa_list = json.loads(clean_json)
                    break  # Success
                    
                except Exception as e:
                    if "429" in str(e) or "RESOURCE" in str(e):
                        wait_time = (attempt + 1) * 30
                        print(f"      ⚠️ Rate limit hit. Waiting {wait_time}s ({attempt+1}/{max_retries})...")
                        for _ in range(wait_time):
                            if is_cancelled():
                                print("🛑 [Auto QA] Cancelled by user.")
                                return
                            time.sleep(1)
                    else:
                        print(f"      ⚠️ Error: {e}")
                        break
            
            if not qa_list:
                print(f"      ❌ Failed to generate for chunk {chunk_idx + 1}")
                continue
            
            # Save to DB
            with engine.connect() as conn:
                saved_count = 0
                for item in qa_list:
                    q = item.get("q")
                    a = item.get("a")
                    if q and a:
                        vec = embeddings.embed_query(q)
                        conn.execute(
                            text("INSERT INTO correct_answers (question, answer, embedding) VALUES (:q, :a, :v)"),
                            {"q": q, "a": a, "v": str(vec)}
                        )
                        saved_count += 1
                conn.commit()
                
            print(f"      ✅ Saved {saved_count} Q&A pairs")
            file_qa_count += saved_count
            remaining_qa -= saved_count
            total_added += saved_count
        
        print(f"\n   📊 File '{fname}': {file_qa_count} Q&A pairs generated")

    print(f"\n🎉 Total {total_added} Q&A pairs generated!")

if __name__ == "__main__":
    generate_bulk_qa()
