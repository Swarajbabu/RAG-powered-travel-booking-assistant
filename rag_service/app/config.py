import os
from pathlib import Path

from dotenv import load_dotenv


RAG_SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = RAG_SERVICE_DIR.parent

load_dotenv(RAG_SERVICE_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

MONGODB_ATLAS = os.getenv("MONGODB_ATLAS")
RAG_SERVICE_SECRET = os.getenv("RAG_SERVICE_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
ATLAS_VECTOR_INDEX = os.getenv(
    "ATLAS_VECTOR_INDEX",
    "rag_vector_index",
)

DOCUMENTS_DIR = PROJECT_ROOT / "documents"
PORT = int(os.getenv("PORT", "8000"))

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVAL_COUNT = 5