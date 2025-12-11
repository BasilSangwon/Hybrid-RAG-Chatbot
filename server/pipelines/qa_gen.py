import os
import json
import time
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from sqlalchemy import text

from server.core.config import RAW_DATA_DIR, GOOGLE_API_KEY
from server.core.database import engine
from server.services.embedder import get_bge_m3_embedding

def generate_bulk_qa(filename=None, model_name="gemini-2.0-flash"):
    print(f"🤖 [Auto QA] Generating Q&A from PDFs using {model_name}...")
    
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
        print(f"\n📄 Analyzing '{fname}'...")
        file_path = os.path.join(RAW_DATA_DIR, fname)
        
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
        full_text = "\n".join([d.page_content for d in docs])
        context = full_text[:10000]

        # 3. Generate Q&A
        print("   ⏳ Generating questions...")
        prompt = f"""
        Analyze the manual below and generate 10 pairs of Question and Answer.
        
        [Manual Content]
        {context}

        [Rules]
        1. **Analyze the language of the manual completely.** (Most likely Korean)
        2. Generate questions and answers in the **SAME language** as the manual.
        3. Diverse questions (How-to, Troubleshooting, Specs).
        4. Answers based on the manual.
        5. Output strictly in JSON list format.

        [Example]
        [
            {{"q": "배터리 교체 방법이 무엇인가요?", "a": "후면 커버를 열고..."}},
            {{"q": "초기화 방법", "a": "설정 > 일반 > 초기화 메뉴 진입"}}
        ]
        """

        # [NEW] Rate Limiting Sleep (Base 15s)
        if total_added >= 0: 
            print("   💤 Cooling down for API rate limit (15s)...")
            time.sleep(15)

        try:
             # [NEW] Simple Retry Logic
            qa_list = []
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    msg = [HumanMessage(content=prompt)]
                    res = llm.invoke(msg).content
                    
                    clean_json = res.replace("```json", "").replace("```", "").strip()
                    qa_list = json.loads(clean_json)
                    break # Success
                except Exception as e:
                    if "429" in str(e) or "RESOURCE" in str(e):
                        wait_time = (attempt + 1) * 30 
                        print(f"   ⚠️ Rate limit hit. Waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        raise e 
            else:
                 print(f"   ❌ Failed after {max_retries} retries for {filename}.")
                 continue

            # 4. Save to DB
            with engine.connect() as conn:
                count = 0
                for item in qa_list:
                    q = item.get("q")
                    a = item.get("a")
                    if q and a:
                        vec = embeddings.embed_query(q)
                        conn.execute(
                            text("INSERT INTO correct_answers (question, answer, embedding) VALUES (:q, :a, :v)"),
                            {"q": q, "a": a, "v": str(vec)}
                        )
                        count += 1
                conn.commit()
                print(f"   ✅ {count} Q&A pairs saved.")
                total_added += count

        except Exception as e:
            print(f"   ⚠️ Error: {e}")

    print(f"\n🎉 Total {total_added} Q&A pairs generated!")

if __name__ == "__main__":
    generate_bulk_qa()
