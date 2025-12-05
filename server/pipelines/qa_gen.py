import os
import json
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from sqlalchemy import text

from server.core.config import RAW_DATA_DIR, GOOGLE_API_KEY
from server.core.database import engine
from server.services.embedder import get_bge_m3_embedding

def generate_bulk_qa():
    print("🤖 [Auto QA] Generating Q&A from PDFs...")
    
    # 1. Prepare Components
    embeddings = get_bge_m3_embedding()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY
    )

    # 2. Check Files
    files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.pdf')]
    if not files:
        print("❌ No PDF files found.")
        return

    total_added = 0

    for filename in files:
        print(f"\n📄 Analyzing '{filename}'...")
        file_path = os.path.join(RAW_DATA_DIR, filename)
        
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
        1. Diverse questions (How-to, Troubleshooting, Specs).
        2. Answers based on the manual.
        3. Output strictly in JSON list format.

        [Example]
        [
            {{"q": "How to replace battery?", "a": "Open back cover..."}},
            {{"q": "Reset method", "a": "Settings > General > Reset"}}
        ]
        """

        try:
            msg = [HumanMessage(content=prompt)]
            res = llm.invoke(msg).content
            
            clean_json = res.replace("```json", "").replace("```", "").strip()
            qa_list = json.loads(clean_json)

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
