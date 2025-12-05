import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(server_dir)
RAW_DATA_DIR = os.path.join(project_root, "data", "raw")

# Database
DB_CONNECTION = "postgresql+psycopg2://postgres:password@localhost:5433/rag_db"
COLLECTION_NAME = "manual_docs"

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Google API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Create necessary directories
os.makedirs(RAW_DATA_DIR, exist_ok=True)
