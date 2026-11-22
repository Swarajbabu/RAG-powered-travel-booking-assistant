from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

try:
    from .app.config import (
        ATLAS_VECTOR_INDEX,
        GEMINI_API_KEY,
        GEMINI_MODEL,
        MONGODB_ATLAS,
        RAG_SERVICE_SECRET,
        RETRIEVAL_COUNT,
    )
    from .app.embeddings import generate_embedding, get_embedding_model
    from .app.gemini import generate_grounded_answer
    from .app.mongo import connect_to_collection
    from .app.retrieval import retrieve_chunks
except ImportError:
    from app.config import (
        ATLAS_VECTOR_INDEX,
        GEMINI_API_KEY,
        GEMINI_MODEL,
        MONGODB_ATLAS,
        RAG_SERVICE_SECRET,
        RETRIEVAL_COUNT,
    )
    from app.embeddings import generate_embedding, get_embedding_model
    from app.gemini import generate_grounded_answer
    from app.mongo import connect_to_collection
    from app.retrieval import retrieve_chunks


app = FastAPI(title="Wanderlust RAG Service", version="0.2.0")
_mongo_client = None
_rag_collection = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=4)
    pageContext: str = Field(default="", max_length=500)
    language: Literal["en"] = "en"


class ChatSource(BaseModel):
    documentId: str
    sourceFile: str
    pageNumber: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    confidence: Literal["high", "low"]
    grounded: bool


def get_collection():
    global _mongo_client, _rag_collection
    if _rag_collection is None:
        if not MONGODB_ATLAS:
            raise RuntimeError("MONGODB_ATLAS is not configured")
        _mongo_client, _rag_collection = connect_to_collection(MONGODB_ATLAS)
    return _rag_collection


def verify_service_key(x_rag_service_key: str | None) -> None:
    if not RAG_SERVICE_SECRET or x_rag_service_key != RAG_SERVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid RAG service key")


@app.on_event("startup")
def warm_embedding_model():
    get_embedding_model()


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_rag_service_key: str | None = Header(default=None),
):
    verify_service_key(x_rag_service_key)

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question is required")

    try:
        question_embedding = generate_embedding(question)
        chunks = retrieve_chunks(
            get_collection(),
            question_embedding,
            limit=RETRIEVAL_COUNT,
            index_name=ATLAS_VECTOR_INDEX,
        )

        if not chunks:
            return ChatResponse(
                answer="I could not find reliable information about that in the Wanderlust documents.",
                sources=[],
                confidence="low",
                grounded=False,
            )

        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        answer = generate_grounded_answer(
            question=question,
            chunks=chunks,
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
        )

        sources = []
        seen = set()
        for chunk in chunks:
            source_key = (chunk.get("sourceFile"), chunk.get("pageNumber"))
            if source_key in seen:
                continue
            seen.add(source_key)
            sources.append(ChatSource(
                documentId=str(chunk.get("documentId", "")),
                sourceFile=str(chunk["sourceFile"]),
                pageNumber=int(chunk["pageNumber"]),
            ))

        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence="high",
            grounded=True,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="RAG service is temporarily unavailable")
