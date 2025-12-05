import os
import sys
from sqlalchemy import create_engine, text
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector

from server.core.config import DB_CONNECTION, RAW_DATA_DIR
from server.core.database import engine
from server.services.embedder import get_bge_m3_embedding

def run_ingest(collection_name: str, chunk_size: int = 1000, overlap: int = 100):
    print(f"\n🏗️  [Ingest] Vector Ingestion Started | Target: {collection_name} | Chunk: {chunk_size} | Overlap: {overlap}")
    
    # 1. Prepare Model
    embeddings = get_bge_m3_embedding()
    
    # 2. Check Files
    if not os.path.exists(RAW_DATA_DIR):
        print(f"❌ Error: '{RAW_DATA_DIR}' folder missing.")
        return

    files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.pdf')]
    if not files:
        print("❌ Error: No PDF files found.")
        return

    # 3. DB Cleanup & Extensions
    print("🧹 [DB] Cleaning up and enabling extensions...")
    try:
        with engine.connect() as conn:
            # Note: We are NOT dropping the table here because we might want to keep other collections.
            # If we want to clean up THIS collection, PGVector usually handles overwrites or we can delete by collection_id.
            # For now, we assume a fresh collection name means a fresh start.
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_bigm"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        print("   ✅ DB Prepared.")
    except Exception as e:
        print(f"   ⚠️ Cleanup Error (Ignorable): {e}")

    # 4. Connect PGVector
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name, # Use dynamic collection name
        connection=DB_CONNECTION,
        use_jsonb=True,
    )

    # 5. Process Files
    total_docs = []
    for filename in files:
        file_path = os.path.join(RAW_DATA_DIR, filename)
        print(f"\n📄 [Parsing] Processing {filename}...")
        
        loader = PyMuPDFLoader(file_path)
        raw_docs = loader.load()
        
        # Use explicit params
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        chunks = text_splitter.split_documents(raw_docs)
        
        for chunk in chunks:
            chunk.metadata["source"] = filename
        
        total_docs.extend(chunks)
        print(f"   ✅ {len(chunks)} Chunks created.")

    # 6. Save to DB
    if total_docs:
        print(f"\n💾 [DB] Saving {len(total_docs)} documents...")
        BATCH_SIZE = 100
        for i in range(0, len(total_docs), BATCH_SIZE):
            batch = total_docs[i : i + BATCH_SIZE]
            vector_store.add_documents(batch)
            print(f"   📦 {min(i + BATCH_SIZE, len(total_docs))}/{len(total_docs)} Saved")
        
        # Create Index
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS bigm_idx ON langchain_pg_embedding USING GIN (document gin_bigm_ops)"))
                conn.commit()
            print("   ✅ pg_bigm index created.")
        except: pass

        print("\n🎉 [Success] Vector Ingestion Complete!")
    else:
        print("⚠️ No data to save.")

if __name__ == "__main__":
    # Default for manual run
    run_ingest(collection_name="manual_run", chunk_size=1000, overlap=100)
