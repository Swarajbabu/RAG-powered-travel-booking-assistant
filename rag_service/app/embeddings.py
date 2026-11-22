from sentence_transformers import SentenceTransformer

from .config import EMBEDDING_MODEL


_model = None


def get_embedding_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)

    return _model


def generate_embedding(text):
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text.")

    model = get_embedding_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


def generate_embeddings(texts):
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return [embedding.tolist() for embedding in embeddings]